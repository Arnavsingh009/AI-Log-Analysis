import os
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.models import LogPayload
from app.database import init_db, SessionLocal, IncidentModel
from app.services.ai_service import analyze_stack_trace
from app.services.cache import generate_signature, get_cached_rca, set_cached_rca
from app.services.alerting import send_alert_webhook

app = FastAPI(title="AI Log Triage Engine", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema
init_db()

# Telemetry counters
metrics_db = {
    "total_logs": 0,
    "cache_hits": 0,
    "cache_misses": 0,
}


def process_error_triage(payload_dict: dict, incident_id: str):
    """Executes AI triage in background, saves to SQLite, and fires alerts."""
    service = payload_dict.get("service_name", "unknown")
    msg = payload_dict.get("message", "")
    stack = payload_dict.get("stack_trace") or msg

    print(f"🚀 [WORKER STARTED] Triage started for {service} (ID: {incident_id[:8]})")

    try:
        sig = generate_signature(service, msg, stack)
        cached = get_cached_rca(sig)

        if cached:
            print(f"⚡ [CACHE HIT] Using cached diagnosis for {service}")
            metrics_db["cache_hits"] += 1
            analysis = cached
        else:
            print(f"🔍 [AI TRIAGE] Calling Groq LLM for {service}...")
            metrics_db["cache_misses"] += 1
            analysis = analyze_stack_trace(service, msg, stack)
            set_cached_rca(sig, analysis)

    except Exception as exc:
        print(f"❌ [WORKER EXCEPTION]: {exc}")
        analysis = {
            "root_cause": f"Triage worker failure: {str(exc)}",
            "affected_component": service,
            "severity": "CRITICAL",
            "suggested_fix": "Inspect Groq LLM configuration and background logs.",
        }

    # Persist diagnosis into SQLite
    db = SessionLocal()
    try:
        incident = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if incident:
            incident.ai_analysis_json = json.dumps(analysis)
            incident.status = "Investigating"
            db.commit()
            print(f"✅ [SUCCESS] Incident {incident_id[:8]} updated in DB.")
    finally:
        db.close()

    # Trigger webhook for High / Critical events
    if analysis.get("severity") in ["CRITICAL", "HIGH"]:
        send_alert_webhook(service, msg, analysis)


@app.post("/api/v1/logs")
async def ingest_log(payload: LogPayload, background_tasks: BackgroundTasks):
    metrics_db["total_logs"] += 1
    log_dict = payload.model_dump()

    lvl = str(getattr(payload.level, "value", payload.level)).strip().upper()

    if lvl in ["ERROR", "CRITICAL"]:
        incident_id = str(uuid.uuid4())
        db = SessionLocal()
        try:
            new_incident = IncidentModel(
                id=incident_id,
                service_name=payload.service_name,
                level=lvl,
                message=payload.message,
                stack_trace=payload.stack_trace or "",
                timestamp=payload.timestamp.strftime("%I:%M:%S %p"),
                status="Open",
                ai_analysis_json=None,
            )
            db.add(new_incident)
            db.commit()
        finally:
            db.close()

        background_tasks.add_task(process_error_triage, log_dict, incident_id)

    return {"status": "accepted"}


@app.get("/api/v1/incidents")
async def get_incidents():
    db = SessionLocal()
    try:
        incidents = db.query(IncidentModel).order_by(IncidentModel.created_at.desc()).all()
        return [i.to_dict() for i in incidents]
    finally:
        db.close()


@app.patch("/api/v1/incidents/{incident_id}")
async def update_status(incident_id: str, body: dict):
    db = SessionLocal()
    try:
        incident = db.query(IncidentModel).filter(IncidentModel.id == incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        incident.status = body.get("status", "Open")
        db.commit()
        return incident.to_dict()
    finally:
        db.close()


@app.get("/api/v1/metrics")
async def get_metrics():
    db = SessionLocal()
    try:
        total_incidents = db.query(IncidentModel).count()
        open_incidents = db.query(IncidentModel).filter(IncidentModel.status != "Resolved").count()
        resolved_incidents = db.query(IncidentModel).filter(IncidentModel.status == "Resolved").count()
        
        cache_total = metrics_db["cache_hits"] + metrics_db["cache_misses"]
        cache_ratio = round((metrics_db["cache_hits"] / cache_total) * 100, 2) if cache_total > 0 else 0.0

        return {
            "total_logs_ingested": metrics_db["total_logs"],
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "resolved_incidents": resolved_incidents,
            "cache_hits": metrics_db["cache_hits"],
            "cache_misses": metrics_db["cache_misses"],
            "cache_hit_ratio_percent": cache_ratio,
        }
    finally:
        db.close()


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Dashboard template missing")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()