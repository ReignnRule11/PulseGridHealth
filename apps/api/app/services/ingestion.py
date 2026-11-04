import csv
import io
import math
from app.schemas import ObservationIn

REQUIRED = {
    "domain", "group_code", "source_code", "observed_date",
    "indicator", "value", "denominator", "unit"
}

def parse_csv(content: bytes, max_bytes: int = 5 * 1024 * 1024):
    if len(content) > max_bytes:
        raise ValueError("upload_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("csv_must_be_utf8") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != REQUIRED:
            raise ValueError("invalid_csv_columns")
        accepted, errors = [], []
        for line_number, row in enumerate(reader, start=2):
            try:
                if None in row:
                    raise ValueError("extra_columns")
                if row.get("denominator") in (None, ""):
                    row["denominator"] = None
                else:
                    row["denominator"] = int(row["denominator"])
                row["value"] = float(row["value"])
                if not math.isfinite(row["value"]):
                    raise ValueError("value_must_be_finite")
                accepted.append(ObservationIn.model_validate(row))
            except Exception as exc:
                errors.append(f"line_{line_number}: {type(exc).__name__}")
        return accepted, errors
    except csv.Error as exc:
        raise ValueError("malformed_csv") from exc
