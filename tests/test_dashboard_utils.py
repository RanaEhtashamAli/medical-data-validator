"""Tests for medical_data_validator/dashboard/utils.py.

Covers the file-format branches of `load_data` and
`dataframe_from_upload_bytes`, and the "no issues" / "missing values
present" branches of `generate_charts`.

Explicitly out of scope (per the Task 11 brief):
- lines 19-21, 26-28: import-fallback branches for a missing
  `medical_data_validator.core` / `plotly` install. Both packages are
  installed in this environment; breaking the import to exercise the
  fallback isn't worth it.
- line 83: the `px is None` short-circuit in `generate_charts`, which
  depends on the same plotly import fallback above.
- line 168: `generate_charts`'s zero-dtype-column message branch. A
  DataFrame with zero columns is practically unreachable through this
  app's real upload/validate flow.
"""

import base64
import io

import numpy as np
import pandas as pd
import pytest

from medical_data_validator.core import ValidationIssue, ValidationResult
from medical_data_validator.dashboard.utils import (
    dataframe_from_upload_bytes,
    generate_charts,
    load_data,
)


def _parquet_engine_available() -> bool:
    try:
        import pyarrow  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        import fastparquet  # noqa: F401

        return True
    except ImportError:
        return False


def _decode_plotly_array(value):
    """Decode a plotly `to_dict()` array field.

    Newer plotly versions (installed here: 6.9.0) compact numeric arrays
    in `Figure.to_dict()` output as {'dtype': ..., 'bdata': <base64>}
    instead of plain lists. Handle both shapes so assertions check real
    decoded values rather than the encoding wrapper.
    """
    if isinstance(value, dict) and "bdata" in value:
        raw = base64.b64decode(value["bdata"])
        return np.frombuffer(raw, dtype=value["dtype"])
    return np.asarray(value)


class TestLoadDataFileFormats:
    """dashboard/utils.py's load_data() — xlsx/parquet/unsupported branches."""

    def test_load_xlsx_file(self, tmp_path):
        df_original = pd.DataFrame(
            {
                "patient_id": ["001", "002", "003"],
                "age": [30, 45, 60],
                "diagnosis": ["A01.1", "B02.2", "C03.3"],
            }
        )
        xlsx_path = tmp_path / "data.xlsx"
        df_original.to_excel(xlsx_path, index=False)

        df = load_data(str(xlsx_path))

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["patient_id", "age", "diagnosis"]
        assert df["age"].tolist() == [30, 45, 60]
        assert df["diagnosis"].tolist() == ["A01.1", "B02.2", "C03.3"]

    def test_load_parquet_file_without_engine_raises_import_error(self, tmp_path):
        """Exercises load_data's '.parquet' branch (calls pd.read_parquet).

        This project declares no parquet engine dependency (pyproject.toml
        has no pyarrow/fastparquet, and .venv has neither installed) --
        consistent with the gap Task 4/5 documented for the /api endpoints
        and cli.load_data. Calling pd.read_parquet() still executes the
        branch line even though no engine is present, so it raises
        ImportError before ever touching the (nonexistent/invalid) file
        contents. If a parquet engine is ever added to the environment,
        this test is skipped rather than failing, since the ImportError
        would no longer occur.
        """
        if _parquet_engine_available():
            pytest.skip("a parquet engine is installed; pd.read_parquet won't raise ImportError")

        parquet_path = tmp_path / "data.parquet"
        parquet_path.write_bytes(b"not a real parquet file")

        with pytest.raises(ImportError):
            load_data(str(parquet_path))

    def test_load_unsupported_format_raises_value_error(self, tmp_path):
        txt_path = tmp_path / "data.txt"
        txt_path.write_text("not a supported format")

        with pytest.raises(ValueError, match="Unsupported file format"):
            load_data(str(txt_path))


class TestDataframeFromUploadBytes:
    """dashboard/utils.py's dataframe_from_upload_bytes() — xlsx/json/unsupported."""

    def test_xlsx_bytes_are_parsed(self):
        df_original = pd.DataFrame(
            {"patient_id": ["001", "002"], "age": [30, 45]}
        )
        buf = io.BytesIO()
        df_original.to_excel(buf, index=False)
        raw_bytes = buf.getvalue()

        parsed = dataframe_from_upload_bytes("upload.xlsx", raw_bytes)

        assert isinstance(parsed, pd.DataFrame)
        assert list(parsed.columns) == ["patient_id", "age"]
        assert parsed["age"].tolist() == [30, 45]

    def test_json_bytes_are_parsed(self):
        df_original = pd.DataFrame(
            {
                "patient_id": ["P001", "P002"],
                "age": [30, 45],
                "diagnosis": ["A01.1", "B02.2"],
            }
        )
        raw_bytes = df_original.to_json(orient="records").encode("utf-8")

        parsed = dataframe_from_upload_bytes("upload.json", raw_bytes)

        assert isinstance(parsed, pd.DataFrame)
        assert list(parsed.columns) == ["patient_id", "age", "diagnosis"]
        assert parsed["patient_id"].tolist() == ["P001", "P002"]
        assert parsed["age"].tolist() == [30, 45]

    def test_unsupported_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file type: upload.txt"):
            dataframe_from_upload_bytes("upload.txt", b"irrelevant content")

    def test_no_extension_raises_value_error(self):
        """filename.rsplit('.', 1) with no '.' leaves suffix == '', hitting
        the same unsupported-format else branch."""
        with pytest.raises(ValueError, match="Unsupported file type: uploadnoextension"):
            dataframe_from_upload_bytes("uploadnoextension", b"irrelevant content")


class TestGenerateCharts:
    """dashboard/utils.py's generate_charts() -- 'no issues' and 'missing
    values present' branches."""

    def test_no_issues_produces_placeholder_severity_chart(self):
        data = pd.DataFrame({"patient_id": ["001", "002"], "age": [30, 45]})
        result = ValidationResult(is_valid=True, issues=[], summary={})

        charts = generate_charts(data, result)

        severity_chart = charts["severity_distribution"]
        assert severity_chart["data"][0]["type"] == "pie"
        assert severity_chart["data"][0]["labels"] == ["No Issues Found"]
        assert severity_chart["data"][0]["values"] == [1]
        assert severity_chart["layout"]["title"] == "Validation Issues by Severity"
        assert severity_chart["layout"]["showlegend"] is False

        # This DataFrame has no missing values, so it also hits the
        # "no missing values" else branch -- already-covered territory,
        # but asserting it keeps this test's fixture self-consistent.
        assert charts["missing_values"]["data"][0]["x"] == ["No Missing Values"]

    def test_issues_present_produces_real_severity_pie(self):
        data = pd.DataFrame({"patient_id": ["001", "002"], "age": [30, 45]})
        result = ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(severity="error", message="bad value", column="age"),
                ValidationIssue(severity="warning", message="check me", column="age"),
            ],
            summary={},
        )

        charts = generate_charts(data, result)

        severity_chart = charts["severity_distribution"]
        # Real px.pie output (not the placeholder message chart): the
        # placeholder never sets a 'marker.colors' keyed by severity name,
        # and px.pie's trace type is still 'pie' but with 2 non-zero values.
        assert severity_chart["data"][0]["type"] == "pie"
        assert sorted(_decode_plotly_array(severity_chart["data"][0]["values"])) == [1, 1]
        assert sorted(severity_chart["data"][0]["labels"]) == ["Error", "Warning"]

        assert charts["column_issues"]["data"][0]["type"] == "bar"
        assert list(_decode_plotly_array(charts["column_issues"]["data"][0]["x"])) == ["age"]

    def test_missing_values_present_produces_real_bar_chart(self):
        data = pd.DataFrame(
            {
                "patient_id": ["001", "002", "003"],
                "age": [30, None, 60],
                "diagnosis": [None, None, "C03.3"],
            }
        )
        result = ValidationResult(is_valid=True, issues=[], summary={})

        charts = generate_charts(data, result)

        missing_chart = charts["missing_values"]
        assert missing_chart["data"][0]["type"] == "bar"
        assert missing_chart["layout"]["title"] == {"text": "Missing Values by Column"}

        x_values = list(_decode_plotly_array(missing_chart["data"][0]["x"]))
        y_values = list(_decode_plotly_array(missing_chart["data"][0]["y"]))
        missing_by_column = dict(zip(x_values, y_values))

        assert missing_by_column["patient_id"] == 0
        assert missing_by_column["age"] == 1
        assert missing_by_column["diagnosis"] == 2
