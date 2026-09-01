from fastapi import FastAPI, BackgroundTasks, HTTPException
from app.models import LogPayload
from app.services.ai_service import analyze_stack_trace
from app.services.cache import generate_signature, get_cached_rca, set_cached_rca
from datetime import datetime
import uuid

app = FastAPI(title="AI Log Triage Engine")

logs_db = []
incidents_db = {}

def process_error_triage(log: LogPayload, incident_id: str):
    sig = generate_signature(log.service_name, log.message, log.stack_trace or "")
    
    # 1. Check Redis Cache
    cached_analysis = get_cached_rca(sig)
    if cached_analysis:
        print(f"⚡ [CACHE HIT] Using cached diagnosis for {log.service_name}")
        analysis = cached_analysis
    else:
        # 2. Call AI Inference
        print(f"🔍 [AI TRIAGE] Requesting LLM diagnosis for {log.service_name}...")
        analysis = analyze_stack_trace(log.service_name, log.message, log.stack_trace or "")
        set_cached_rca(sig, analysis)
    
    # Update incident record
    if incident_id in incidents_db:
        incidents_db[incident_id]["ai_analysis"] = analysis
        incidents_db[incident_id]["status"] = "Investigating"

@app.get("/")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/api/v1/incidents")
def get_incidents():
    """Retrieve all triage incidents with their status and AI reports."""
    return {"total_incidents": len(incidents_db), "incidents": list(incidents_db.values())}

@app.patch("/api/v1/incidents/{incident_id}/status")
def update_status(incident_id: str, status: str):
    """Update incident status: Open, Investigating, Resolved"""
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    if status not in ["Open", "Investigating", "Resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    incidents_db[incident_id]["status"] = status
    return {"message": f"Incident updated to {status}", "incident": incidents_db[incident_id]}

@app.post("/api/v1/logs")
async def ingest_log(log: LogPayload, background_tasks: BackgroundTasks):
    logs_db.append(log)
    incident_id = None
    
    if log.level in ["ERROR", "CRITICAL"] and log.stack_trace:
        incident_id = str(uuid.uuid4())
        incidents_db[incident_id] = {
            "id": incident_id,
            "timestamp": log.timestamp,
            "service": log.service_name,
            "level": log.level,
            "raw_error": log.message,
            "status": "Open",
            "ai_analysis": None
        }
        background_tasks.add_task(process_error_triage, log, incident_id)
        
    return {
        "status": "received",
        "service": log.service_name,
        "incident_id": incident_id,
        "logged_at": log.timestamp
    }