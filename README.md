

### Local `env` for `docs`

``` shell

```
# Autonomous AI Log Triage & Root Cause Analysis Engine

An event-driven log ingestion and automated incident triage pipeline built for modern microservice architectures. Powered by **FastAPI**, **Groq LLM (`llama3-8b-8192`)**, and **Redis caching**, this platform intercepts distributed system telemetry, performs deduplication, diagnoses runtime stack traces asynchronously, and streams actionable mitigation steps to a real-time SRE incident dashboard.

---

## Features

- **Fast Ingestion Gateway:** Asynchronous FastAPI endpoint (`POST /api/v1/logs`) validating incoming telemetry against strict Pydantic schemas.
- **Automated Root Cause Analysis (RCA):** Unseen crash traces trigger an asynchronous background task leveraging Groq's Llama 3 engine to produce structured JSON root causes, affected components, severity ratings, and remediation steps.
- **Crash Deduplication & Caching:** SHA-256 crash signature hashing paired with Redis caching ensures repeated errors bypass LLM overhead, optimizing latency down to sub-millisecond lookups.
- **Live SRE Command Dashboard:** Interactive dark-mode dashboard (`/dashboard`) with automatic polling, incident lifecycle management (Open -> Investigating -> Resolved), and severity tracking.
- **Traffic Simulator:** Standalone generator script simulating production traffic patterns across multiple microservices (`payment-service`, `auth-service`, `inventory-service`, `order-service`).
- **Automated Test Suite:** Unit testing for health checks, schema validation, and triage workflows via `pytest`.

---

## Architecture Overview
