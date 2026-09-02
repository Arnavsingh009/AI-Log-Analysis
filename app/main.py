import os
import uuid
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.models import LogPayload
from app.services.ai_service import analyze_stack_trace
from app.services.cache import generate_signature, get_cached_rca, set_cached_rca

app = FastAPI(title="AI Log Triage Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
logs_db = []
incidents_db = {}


def process_error_triage(log: LogPayload, incident_id: str):
    """Background task to run AI RCA and update the incident."""
    stack = log.stack_trace or log.message
    sig = generate_signature(log.service_name, log.message, stack)

    # 1. Check Redis cache
    cached_analysis = get_cached_rca(sig)
    if cached_analysis:
        print(f"⚡ [CACHE HIT] Using cached diagnosis for {log.service_name}")
        analysis = cached_analysis
    else:
        # 2. Call Groq AI
        print(f"🔍 [AI TRIAGE] Requesting LLM diagnosis for {log.service_name}...")
        analysis = analyze_stack_trace(log.service_name, log.message, stack)
        set_cached_rca(sig, analysis)

    # 3. Update Incident State
    if incident_id in incidents_db:
        incidents_db[incident_id]["ai_analysis"] = analysis
        incidents_db[incident_id]["status"] = "Investigating"
        print(f"✅ Incident {incident_id} successfully updated with AI diagnosis.")


@app.post("/api/v1/logs")
async def ingest_log(payload: LogPayload, background_tasks: BackgroundTasks):
    log_dict = payload.model_dump()
    logs_db.append(log_dict)

    if payload.level.upper() in ["ERROR", "CRITICAL"]:
        incident_id = str(uuid.uuid4())
        incidents_db[incident_id] = {
            "id": incident_id,
            "service_name": payload.service_name,
            "level": payload.level.upper(),
            "message": payload.message,
            "stack_trace": payload.stack_trace,
            "timestamp": payload.timestamp.strftime("%I:%M:%S %p"),
            "status": "Open",
            "ai_analysis": None,
        }
        background_tasks.add_task(process_error_triage, payload, incident_id)

    return {"status": "accepted"}


@app.get("/api/v1/incidents")
async def get_incidents():
    return list(reversed(list(incidents_db.values())))


@app.patch("/api/v1/incidents/{incident_id}")
async def update_status(incident_id: str, body: dict):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    incidents_db[incident_id]["status"] = body.get("status", "Open")
    return incidents_db[incident_id]


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Dashboard template missing")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()