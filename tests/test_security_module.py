"""Pure-unit tests for medical_data_validator.security.

Covers DataAnonymizer, SecurityAuditor._check_file_permissions, DataSanitizer's
NaN handling, and filename validation/sanitization. None of these need a Flask
app or test client - see tests/test_security_endpoints.py and
tests/test_flask_api_security.py for the /api/security/* endpoint tests.
"""

import os
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from medical_data_validator.security import DataAnonymizer, DataSanitizer, SecurityAuditor


# ---------------------------------------------------------------------------
# DataAnonymizer.anonymize_column - method dispatch + hipaa_safe_harbor branches
# ---------------------------------------------------------------------------

class TestAnonymizeColumnDispatch:
    def test_hash_method_dispatches_to_hash_anonymization(self):
        anonymizer = DataAnonymizer(method="hash")
        result = anonymizer.anonymize_column(pd.Series(["value"]), "whatever_column")
        assert len(result[0]) == 8
        assert result[0] != "value"

    def test_mask_method_dispatches_to_mask_anonymization(self):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer.anonymize_column(pd.Series(["5551234567"]), "phone")
        assert result[0] == "***-***-4567"

    def test_unknown_method_raises_value_error(self):
        anonymizer = DataAnonymizer(method="not_a_real_method")
        with pytest.raises(ValueError, match="Unknown anonymization method"):
            anonymizer.anonymize_column(pd.Series(["x"]), "col")

    def test_hash_method_nan_value_returns_none(self):
        anonymizer = DataAnonymizer(method="hash")
        result = anonymizer.anonymize_column(pd.Series([np.nan, "value"]), "col")
        # hash_value() returns None for NaN input; under pandas' string dtype
        # (default for object-like Series on pandas >= 3.0) that None is
        # normalized back to a NaN sentinel rather than staying a literal
        # None, so check with pd.isna() instead of `is None`.
        assert pd.isna(result[0])
        assert len(result[1]) == 8


class TestHipaaSafeHarborBranches:
    def test_date_branch_generalizes_to_year(self):
        anonymizer = DataAnonymizer(method="hipaa_safe_harbor")
        col = pd.Series(["2020-01-15", "1999-12-31"])
        result = anonymizer.anonymize_column(col, "birth_date")
        assert list(result) == ["2020", "1999"]

    def test_admission_date_column_name_also_triggers_date_branch(self):
        anonymizer = DataAnonymizer(method="hipaa_safe_harbor")
        col = pd.Series(["2021-06-01"])
        result = anonymizer.anonymize_column(col, "admission_date")
        assert list(result) == ["2021"]

    def test_address_branch_redacts(self):
        anonymizer = DataAnonymizer(method="hipaa_safe_harbor")
        col = pd.Series(["123 Main St", "456 Oak Ave"])
        result = anonymizer.anonymize_column(col, "street_address")
        assert list(result) == ["[REDACTED]", "[REDACTED]"]

    def test_city_column_name_also_triggers_address_branch(self):
        anonymizer = DataAnonymizer(method="hipaa_safe_harbor")
        col = pd.Series(["Springfield"])
        result = anonymizer.anonymize_column(col, "city")
        assert list(result) == ["[REDACTED]"]

    def test_default_branch_hashes_columns_matching_no_pattern(self):
        anonymizer = DataAnonymizer(method="hipaa_safe_harbor")
        col = pd.Series(["diabetes", "hypertension"])
        result = anonymizer.anonymize_column(col, "diagnosis")
        # 8-char hex digests, distinct per distinct input.
        assert all(len(v) == 8 for v in result)
        assert result[0] != result[1]
        # Same instance (same salt) + same value -> same digest, confirming
        # this really went through the hash path and not e.g. a REDACTED path.
        again = anonymizer.anonymize_column(pd.Series(["diabetes"]), "diagnosis")
        assert again[0] == result[0]


# ---------------------------------------------------------------------------
# _mask_anonymization branches
# ---------------------------------------------------------------------------

class TestMaskAnonymization:
    def test_phone_branch(self):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer._mask_anonymization(pd.Series(["5551234567"]), "phone_number")
        assert result[0] == "***-***-4567"

    def test_email_branch_with_at_symbol(self):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer._mask_anonymization(pd.Series(["johndoe@example.com"]), "email")
        assert result[0] == "joh***@example.com"

    def test_email_branch_without_at_symbol_returns_value_unchanged(self):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer._mask_anonymization(pd.Series(["not-an-email"]), "email")
        assert result[0] == "not-an-email"

    def test_else_branch_generic_masking(self):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer._mask_anonymization(pd.Series(["diabetes"]), "diagnosis")
        assert result[0] == "dia***"

    @pytest.mark.parametrize("column_name", ["phone", "ssn", "email", "diagnosis"])
    def test_nan_values_pass_through_unchanged_on_every_branch(self, column_name):
        anonymizer = DataAnonymizer(method="mask")
        result = anonymizer._mask_anonymization(pd.Series([np.nan]), column_name)
        assert pd.isna(result[0])


# ---------------------------------------------------------------------------
# _generalize_date
# ---------------------------------------------------------------------------

class TestGeneralizeDate:
    def setup_method(self):
        self.anonymizer = DataAnonymizer()

    def test_nan_returns_none(self):
        assert self.anonymizer._generalize_date(np.nan) is None
        assert self.anonymizer._generalize_date(None) is None

    def test_iso_format_string(self):
        assert self.anonymizer._generalize_date("2020-01-15") == "2020"

    def test_us_slash_format_string(self):
        assert self.anonymizer._generalize_date("01/15/2020") == "2020"

    def test_day_first_slash_format_string(self):
        # 15 can't be a month, so this only parses under %d/%m/%Y - exercises
        # the third format in the loop.
        assert self.anonymizer._generalize_date("15/01/2020") == "2020"

    def test_year_first_slash_format_string(self):
        assert self.anonymizer._generalize_date("2022/07/04") == "2022"

    def test_unparseable_string_returned_unchanged(self):
        assert self.anonymizer._generalize_date("not-a-date") == "not-a-date"

    def test_datetime_object(self):
        assert self.anonymizer._generalize_date(datetime(2021, 6, 1)) == "2021"

    def test_pandas_timestamp(self):
        assert self.anonymizer._generalize_date(pd.Timestamp("2022-03-04")) == "2022"

    def test_non_date_non_string_value_is_stringified(self):
        assert self.anonymizer._generalize_date(20230101) == "20230101"

    def test_exception_inside_datetime_handling_returns_redacted_sentinel(self):
        # A datetime subclass whose .year raises exercises the method's
        # bare `except: return '[REDACTED]'` fallback - the isinstance()
        # check on line ~199 passes (it *is* a datetime), but reading
        # .year blows up, which is exactly what the bare except guards
        # against.
        class BadDatetime(datetime):
            @property
            def year(self):
                raise RuntimeError("boom")

        bad = BadDatetime(2020, 1, 1)
        assert self.anonymizer._generalize_date(bad) == "[REDACTED]"


# ---------------------------------------------------------------------------
# SecurityAuditor._check_file_permissions
# ---------------------------------------------------------------------------

class TestCheckFilePermissions:
    def setup_method(self):
        self.auditor = SecurityAuditor()

    def _make_temp_file(self, mode):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        os.chmod(path, mode)
        return path

    def test_no_file_path_skips_check_entirely(self):
        result = self.auditor._check_file_permissions(pd.DataFrame(), None)
        assert result == {"issues": [], "recommendations": [], "score_penalty": 0}

    def test_owner_only_permissions_flag_nothing(self):
        path = self._make_temp_file(0o600)
        try:
            result = self.auditor._check_file_permissions(pd.DataFrame(), path)
            assert result["issues"] == []
            assert result["score_penalty"] == 0
        finally:
            os.remove(path)

    def test_world_readable_file_is_flagged(self):
        path = self._make_temp_file(0o644)  # rw-r--r--
        try:
            result = self.auditor._check_file_permissions(pd.DataFrame(), path)
            assert any("world-readable" in issue for issue in result["issues"])
            assert not any("world-writable" in issue for issue in result["issues"])
            assert result["score_penalty"] == 20
            assert any("Restrict file permissions" in rec for rec in result["recommendations"])
        finally:
            os.remove(path)

    def test_world_writable_file_is_flagged_in_addition_to_readable(self):
        path = self._make_temp_file(0o666)  # rw-rw-rw-
        try:
            result = self.auditor._check_file_permissions(pd.DataFrame(), path)
            assert any("world-readable" in issue for issue in result["issues"])
            assert any("world-writable" in issue for issue in result["issues"])
            assert result["score_penalty"] == 50
            assert any("Remove world-write permissions" in rec for rec in result["recommendations"])
        finally:
            os.remove(path)

    def test_nonexistent_file_path_is_caught_as_exception(self):
        result = self.auditor._check_file_permissions(
            pd.DataFrame(), "/definitely/does/not/exist/file.csv"
        )
        assert result["score_penalty"] == 5
        assert any("Could not check file permissions" in issue for issue in result["issues"])


# ---------------------------------------------------------------------------
# DataSanitizer._sanitize_value NaN branch
# ---------------------------------------------------------------------------

class TestSanitizeValueNaN:
    def test_nan_float_returned_unchanged(self):
        sanitizer = DataSanitizer()
        result = sanitizer._sanitize_value(np.nan)
        assert pd.isna(result)

    def test_none_returned_unchanged(self):
        sanitizer = DataSanitizer()
        assert sanitizer._sanitize_value(None) is None

    def test_non_nan_value_is_still_stringified(self):
        # Sanity check that the early-return is specific to NaN/None, not a
        # general pass-through.
        sanitizer = DataSanitizer()
        result = sanitizer._sanitize_value("<script>bad()</script>hi")
        assert result == "hi"


# ---------------------------------------------------------------------------
# validate_filename / sanitize_filename
# ---------------------------------------------------------------------------

DANGEROUS_CHARS = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']


class TestFilenameValidation:
    def setup_method(self):
        self.sanitizer = DataSanitizer()

    def test_safe_filename_is_valid(self):
        assert self.sanitizer.validate_filename("patient_data_2024.csv") is True

    @pytest.mark.parametrize("char", DANGEROUS_CHARS)
    def test_each_dangerous_char_makes_filename_invalid(self, char):
        assert self.sanitizer.validate_filename(f"file{char}name.csv") is False

    def test_safe_filename_is_unchanged_by_sanitize(self):
        assert self.sanitizer.sanitize_filename("patient_data.csv") == "patient_data.csv"

    @pytest.mark.parametrize("char", DANGEROUS_CHARS)
    def test_each_dangerous_char_is_replaced_with_underscore(self, char):
        result = self.sanitizer.sanitize_filename(f"file{char}name.csv")
        assert char not in result
        assert result == "file_name.csv"

    def test_multiple_dangerous_chars_all_replaced(self):
        result = self.sanitizer.sanitize_filename('a<b>c:d"e|f?g*h\\i/j')
        assert result == "a_b_c_d_e_f_g_h_i_j"
        # And the sanitized result is now valid per validate_filename.
        assert self.sanitizer.validate_filename(result) is True
