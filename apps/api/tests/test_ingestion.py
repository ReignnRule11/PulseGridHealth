import io

import pandas as pd
import pytest

from app.services.ingestion import parse_csv, parse_upload


def test_valid_csv_parses():
    content = (
        b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\\n"
        b"community,C001,SYNTH,2026-01-05,weekly_reports,12,5000,count\\n"
    )
    rows, errors = parse_csv(content)
    assert len(rows) == 1
    assert errors == []
    assert rows[0].domain == "community"


def test_csv_header_bom_whitespace_and_decimal_integer_denominator_are_normalized():
    content = (
        "\\ufeff Domain , Group_Code , Source_Code , Observed_Date , Indicator , Value , Denominator , Unit \\n"
        "community,C001,SYNTH,2026-01-05,weekly_reports,12,5000.0,count\\n"
    ).encode("utf-8")
    rows, errors = parse_csv(content)
    assert len(rows) == 1
    assert errors == []
    assert rows[0].denominator == 5000


def test_invalid_columns_rejected():
    with pytest.raises(ValueError, match="invalid_csv_columns"):
        parse_csv(b"name,value\\nfoo,1\\n")


def test_negative_value_rejected_as_row_error():
    content = (
        b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\\n"
        b"community,C001,SYNTH,2026-01-05,weekly_reports,-1,5000,count\\n"
    )
    rows, errors = parse_csv(content)
    assert rows == []
    assert len(errors) == 1
    assert "line_2" in errors[0]


def test_xlsx_upload_parses_first_worksheet():
    frame = pd.DataFrame([{
        "domain": "community", "group_code": "C002", "source_code": "SYNTH",
        "observed_date": "2026-01-05", "indicator": "weekly_reports",
        "value": 12, "denominator": 5000, "unit": "count",
    }])
    stream = io.BytesIO()
    frame.to_excel(stream, index=False, engine="openpyxl")
    rows, errors = parse_upload(stream.getvalue(), "observations.xlsx")
    assert len(rows) == 1
    assert errors == []
    assert rows[0].group_code == "C002"


def test_xls_extension_selects_legacy_excel_reader(monkeypatch):
    called = {}
    def fake_read_excel(*args, **kwargs):
        called.update(kwargs)
        return pd.DataFrame([{
            "domain": "community", "group_code": "C003", "source_code": "SYNTH",
            "observed_date": "2026-01-05", "indicator": "weekly_reports",
            "value": 12, "denominator": 5000, "unit": "count",
        }])
    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    rows, errors = parse_upload(b"test", "observations.xls")
    assert len(rows) == 1 and errors == []
    assert called["engine"] == "xlrd"


def test_unsupported_spreadsheet_typo_is_rejected():
    with pytest.raises(ValueError, match="unsupported_file_type"):
        parse_upload(b"test", "observations.xsl")
