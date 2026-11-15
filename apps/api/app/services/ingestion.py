import csv
import io
import math
from pathlib import Path

import pandas as pd
from app.schemas import ObservationIn

REQUIRED = {
    "domain", "group_code", "source_code", "observed_date",
    "indicator", "value", "denominator", "unit"
}
EXCEL_EXTENSIONS = {".xls", ".xlsx"}
CSV_EXTENSIONS = {".csv"}


def _normalize_headers(fieldnames):
    if not fieldnames:
        raise ValueError("missing_header_row")
    normalized = [str(name or "").strip().lower() for name in fieldnames]
    if len(normalized) != len(set(normalized)) or set(normalized) != REQUIRED:
        missing = sorted(REQUIRED - set(normalized))
        extra = sorted(set(normalized) - REQUIRED)
        raise ValueError(f"invalid_csv_columns: missing={missing}; unexpected={extra}")
    return normalized


def parse_csv(content: bytes, max_bytes: int = 5 * 1024 * 1024):
    if not content:
        raise ValueError("empty_upload")
    if len(content) > max_bytes:
        raise ValueError("upload_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("csv_must_be_utf8") from exc

    try:
        reader = csv.DictReader(io.StringIO(text))
        normalized = _normalize_headers(reader.fieldnames)
        reader.fieldnames = normalized
        accepted, errors = [], []
        for line_number, row in enumerate(reader, start=2):
            if not row or all(value is None or str(value).strip() == "" for value in row.values()):
                continue
            try:
                if None in row:
                    raise ValueError("extra_columns")
                denominator = row.get("denominator")
                if denominator is None or str(denominator).strip() == "":
                    row["denominator"] = None
                else:
                    number = float(denominator)
                    if not math.isfinite(number) or not number.is_integer():
                        raise ValueError("denominator_must_be_positive_integer")
                    row["denominator"] = int(number)
                row["value"] = float(row["value"])
                if not math.isfinite(row["value"]):
                    raise ValueError("value_must_be_finite")
                accepted.append(ObservationIn.model_validate(row))
            except Exception as exc:
                reason = str(exc).splitlines()[0][:160] or type(exc).__name__
                errors.append(f"line_{line_number}: {reason}")
        return accepted, errors
    except csv.Error as exc:
        raise ValueError("malformed_csv") from exc


def parse_excel(content: bytes, filename: str, max_bytes: int = 5 * 1024 * 1024):
    if not content:
        raise ValueError("empty_upload")
    if len(content) > max_bytes:
        raise ValueError("upload_too_large")
    extension = Path(filename).suffix.lower()
    if extension not in EXCEL_EXTENSIONS:
        raise ValueError("unsupported_file_type: use .csv, .xls, or .xlsx")
    engine = "xlrd" if extension == ".xls" else "openpyxl"
    try:
        frame = pd.read_excel(io.BytesIO(content), sheet_name=0, dtype=object, engine=engine)
    except ImportError as exc:
        dependency = "xlrd" if extension == ".xls" else "openpyxl"
        raise ValueError(f"spreadsheet_reader_unavailable: install {dependency}") from exc
    except Exception as exc:
        raise ValueError("invalid_or_unreadable_spreadsheet") from exc

    if len(frame.index) > 50000:
        raise ValueError("spreadsheet_row_limit_exceeded: maximum 50000 data rows")
    # Reuse the exact CSV schema and row validation path for both spreadsheet formats.
    csv_content = frame.to_csv(index=False, na_rep="").encode("utf-8")
    return parse_csv(csv_content, max_bytes=max_bytes)


def parse_upload(content: bytes, filename: str, max_bytes: int = 5 * 1024 * 1024):
    extension = Path(filename or "").suffix.lower()
    if extension in CSV_EXTENSIONS:
        return parse_csv(content, max_bytes=max_bytes)
    if extension in EXCEL_EXTENSIONS:
        return parse_excel(content, filename, max_bytes=max_bytes)
    raise ValueError("unsupported_file_type: use .csv, .xls, or .xlsx")
