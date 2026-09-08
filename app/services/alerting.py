import os
import requests

WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")


def send_alert_webhook(service_name: str, message: str, ai_analysis: dict):
    """Sends an incident notification webhook if a URL is configured."""
    if not WEBHOOK_URL:
        return

    severity = ai_analysis.get("severity", "UNKNOWN")
    root_cause = ai_analysis.get("root_cause", "N/A")
    fix = ai_analysis.get("suggested_fix", "N/A")

    # Discord-compatible embed structure (also functions with generic webhook receivers)
    payload = {
        "content": f"🚨 **[{severity}] Incident Detected in `{service_name}`**",
        "embeds": [
            {
                "title": f"RCA: {service_name}",
                "color": 15158332 if severity == "CRITICAL" else 15105570,
                "fields": [
                    {"name": "Error", "value": f"`{message[:250]}`", "inline": False},
                    {"name": "Root Cause", "value": root_cause, "inline": False},
                    {"name": "Suggested Fix", "value": fix, "inline": False},
                ],
            }
        ],
    }

    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=3)
    except Exception as exc:
        print(f"⚠️ [WEBHOOK FAILED]: {exc}")