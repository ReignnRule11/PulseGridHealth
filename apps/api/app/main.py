from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.services.ingestion import parse_csv
from app.services.detection import robust_anomaly

app = FastAPI(title="PulseGrid Health API", version="0.1.0")

origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.app_env}

@app.post("/api/v1/observations/import")
async def import_observations(file: UploadFile = File(...)):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="csv_only")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        rows, errors = parse_csv(content, settings.max_upload_mb * 1024 * 1024)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Phase 1 scaffold: parsing/validation only. Persistence is added with M1/M2
    # database repository implementation; never report rows as stored here.
    return {"validated": len(rows), "rejected": len(errors), "errors": errors[:50],
            "persistence": "not_yet_implemented"}

@app.post("/api/v1/detection/run")
def run_detection(payload: dict):
    try:
        history = [float(x) for x in payload["history"]]
        current = float(payload["current"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="history_and_current_required") from exc
    result = robust_anomaly(
        history, current,
        min_history=settings.min_baseline_points,
        threshold=settings.anomaly_z_threshold
    )
    return {
        "baseline": result.baseline,
        "anomaly_score": result.anomaly_score,
        "candidate": result.is_candidate,
        "reason": result.reason,
        "model": "median_mad",
        "model_version": "0.1.0",
        "notice": "Statistical signal only; human review required."
    }
