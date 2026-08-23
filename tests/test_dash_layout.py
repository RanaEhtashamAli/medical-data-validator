"""Tests for the Dash callback that validates an uploaded file."""

import base64
import pandas as pd
import dash

# dashboard.pages.validate calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

from tests.conftest import _set_triggered


def _make_upload_contents(df: pd.DataFrame) -> tuple[str, str]:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    b64 = base64.b64encode(csv_bytes).decode("utf-8")
    return f"data:text/csv;base64,{b64}", "test.csv"


def test_dataframe_from_upload_bytes_parses_csv():
    from medical_data_validator.dashboard.utils import dataframe_from_upload_bytes
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    raw = df.to_csv(index=False).encode("utf-8")
    parsed = dataframe_from_upload_bytes("test.csv", raw)
    assert list(parsed.columns) == ["a", "b"]
    assert len(parsed) == 2


def test_update_output_no_upload_returns_placeholder():
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    result = _run_validation_for_upload(None, None, ["phi", "quality"], None)
    assert result[0] == "Upload a file to start validation"


def test_update_output_with_real_upload_calls_validator():
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    df = pd.DataFrame({"ssn": ["123-45-6789", "000-00-0000"], "notes": ["a", "b"]})
    contents, filename = _make_upload_contents(df)

    summary, severity_fig, column_fig, missing_fig, dtype_fig, result_dict = _run_validation_for_upload(
        contents, filename, ["phi", "quality"], None
    )

    assert "coming soon" not in str(summary).lower()
    assert severity_fig != {}
    assert isinstance(severity_fig, dict) and "data" in severity_fig
    for fig in (column_fig, missing_fig, dtype_fig):
        assert fig != {}
    assert result_dict is not None
    assert "is_valid" in result_dict


def test_update_output_with_unparseable_upload_returns_error_message():
    """_run_validation_for_upload's parse-failure branch: dataframe_from_upload_bytes
    raises (unsupported extension) and the callback must catch it and report the
    error instead of propagating, leaving charts empty and no result_dict."""
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    contents = "data:text/plain;base64," + base64.b64encode(b"irrelevant content").decode("utf-8")
    filename = "upload.unsupported"

    summary, severity_fig, column_fig, missing_fig, dtype_fig, result_dict = _run_validation_for_upload(
        contents, filename, ["phi", "quality"], None
    )

    assert summary.startswith(f"Could not parse {filename}:")
    assert "Unsupported file type" in summary
    assert severity_fig == {}
    assert column_fig == {}
    assert missing_fig == {}
    assert dtype_fig == {}
    assert result_dict is None


def _build_real_result_dict():
    """Run real validation on a small DataFrame and return the resulting
    ValidationResult.to_dict(), for use as _download_report's State input."""
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    df = pd.DataFrame({"ssn": ["123-45-6789", "000-00-0000"], "notes": ["a", "b"]})
    contents, filename = _make_upload_contents(df)
    *_rest, result_dict = _run_validation_for_upload(contents, filename, ["phi", "quality"], None)
    assert result_dict is not None
    return result_dict


def test_download_report_without_prior_validation_returns_no_update():
    """not result_dict -> dash.no_update guard, e.g. before any validation has run."""
    from medical_data_validator.dashboard.pages.validate import _download_report
    _set_triggered('download-pdf-btn')
    result = _download_report(1, None, None)
    assert result is dash.no_update


def test_download_report_pdf_button_returns_real_pdf_bytes():
    from medical_data_validator.dashboard.pages.validate import _download_report
    result_dict = _build_real_result_dict()

    _set_triggered('download-pdf-btn')
    payload = _download_report(1, None, result_dict)

    assert isinstance(payload, dict)
    assert payload['filename'] == 'validation_report.pdf'
    assert payload['base64'] is True
    pdf_bytes = base64.b64decode(payload['content'])
    assert pdf_bytes.startswith(b'%PDF')


def test_download_report_csv_button_returns_real_csv_text():
    from medical_data_validator.dashboard.pages.validate import _download_report
    result_dict = _build_real_result_dict()

    _set_triggered('download-csv-btn')
    payload = _download_report(None, 1, result_dict)

    assert isinstance(payload, dict)
    assert payload['filename'] == 'validation_report.csv'
    assert payload['base64'] is False
    assert 'Medical Data Validation Report' in payload['content']
    assert 'severity,rule_name,column,row,message' in payload['content']
