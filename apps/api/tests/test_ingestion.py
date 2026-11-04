import pytest
from app.services.ingestion import parse_csv

def test_valid_csv_parses():
    content = (
        b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
        b"community,C001,SYNTH,2026-01-05,weekly_reports,12,5000,count\n"
    )
    rows, errors = parse_csv(content)
    assert len(rows) == 1
    assert errors == []
    assert rows[0].domain == "community"

def test_invalid_columns_rejected():
    with pytest.raises(ValueError, match="invalid_csv_columns"):
        parse_csv(b"name,value\nfoo,1\n")

def test_negative_value_rejected_as_row_error():
    content = (
        b"domain,group_code,source_code,observed_date,indicator,value,denominator,unit\n"
        b"community,C001,SYNTH,2026-01-05,weekly_reports,-1,5000,count\n"
    )
    rows, errors = parse_csv(content)
    assert rows == []
    assert len(errors) == 1
