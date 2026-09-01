import requests
import time
import random

API_URL = "http://localhost:8000/api/v1/logs"

SERVICES = ["payment-service", "auth-service", "order-service", "inventory-service"]
LOG_LEVELS = ["INFO", "INFO", "INFO", "WARNING", "ERROR"]

ERROR_STACKS = [
    "ConnectionTimeout: Failed to reach https://api.stripe.com at payment.py:42",
    "OperationalError: PostgreSQL connection pool exhausted at db.py:108",
    "KeyError: 'jwt_token' missing in request header at auth_middleware.py:15"
]

def generate_log():
    level = random.choice(LOG_LEVELS)
    service = random.choice(SERVICES)
    
    payload = {
        "service_name": service,
        "level": level,
        "message": f"Operation completed with status {level}",
        "stack_trace": random.choice(ERROR_STACKS) if level == "ERROR" else None
    }
    
    try:
        res = requests.post(API_URL, json=payload)
        print(f"[{res.status_code}] Sent {level} log from {service}")
    except Exception as e:
        print("API offline:", e)

if __name__ == "__main__":
    print("🚀 Simulating microservice log emissions... (Ctrl+C to stop)")
    while True:
        generate_log()
        time.sleep(2)