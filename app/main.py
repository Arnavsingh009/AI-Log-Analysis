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

# In-memory incident and log registries
logs_db = []
incidents_db = {}


def process_error_triage(payload_dict: dict, incident_id: str):
    service = payload_dict.get("service_name", "unknown")
    msg = payload_dict.get("message", "")
    stack = payload_dict.get("stack_trace") or msg

    print(f"🚀 [WORKER STARTED] Triage started for {service} (ID: {incident_id[:8]})")

    try:
        sig = generate_signature(service, msg, stack)
        cached = get_cached_rca(sig)

        if cached:
            print(f"⚡ [CACHE HIT] Using cached diagnosis for {service}")
            analysis = cached
        else:
            print(f"🔍 [AI TRIAGE] Calling Groq LLM for {service}...")
            analysis = analyze_stack_trace(service, msg, stack)
            set_cached_rca(sig, analysis)

    except Exception as exc:
        print(f"❌ [WORKER EXCEPTION]: {exc}")
        analysis = {
            "root_cause": f"Triage worker failure: {str(exc)}",
            "affected_component": service,
            "severity": "CRITICAL",
            "suggested_fix": "Check worker execution and Redis connectivity."
        }

    # Always persist the analysis back to the active incident
    if incident_id in incidents_db:
        incidents_db[incident_id]["ai_analysis"] = analysis
        incidents_db[incident_id]["status"] = "Investigating"
        print(f"✅ [SUCCESS] Incident {incident_id[:8]} updated with diagnosis!")

@app.post("/api/v1/logs")
async def ingest_log(payload: LogPayload, background_tasks: BackgroundTasks):
    log_dict = payload.model_dump()
    logs_db.append(log_dict)

    # Ensure level check works whether string or enum
    lvl = str(getattr(payload.level, "value", payload.level)).strip().upper()
    print(f"📥 Received log: [{lvl}] from {payload.service_name}")

    if lvl in ["ERROR", "CRITICAL"]:
        incident_id = str(uuid.uuid4())
        incidents_db[incident_id] = {
            "id": incident_id,
            "service_name": payload.service_name,
            "level": lvl,
            "message": payload.message,
            "stack_trace": payload.stack_trace or "",
            "timestamp": payload.timestamp.strftime("%I:%M:%S %p"),
            "status": "Open",
            "ai_analysis": None,
        }
        print(f"➕ Registered incident {incident_id[:8]} in memory. Scheduling triage...")
        background_tasks.add_task(process_error_triage, log_dict, incident_id)

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
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)