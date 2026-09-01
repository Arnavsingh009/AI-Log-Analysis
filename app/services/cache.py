import hashlib
import json
import redis
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Initialize Redis client
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def generate_signature(service_name: str, message: str, stack_trace: str) -> str:
    """Creates a deterministic MD5 hash of the error signature."""
    raw_key = f"{service_name}:{message}:{stack_trace}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

def get_cached_rca(signature: str):
    """Retrieve existing RCA diagnosis if present in cache."""
    try:
        data = redis_client.get(f"rca:{signature}")
        if data:
            return json.loads(data)
    except Exception:
        return None
    return None

def set_cached_rca(signature: str, analysis: dict, ttl_seconds: int = 3600):
    """Cache RCA analysis for 1 hour."""
    try:
        redis_client.setex(f"rca:{signature}", ttl_seconds, json.dumps(analysis))
    except Exception:
        pass