import hashlib
import json
from typing import Optional, Dict, Any

# In-memory fallback dictionary
_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}


def generate_signature(service_name: str, message: str, stack_trace: str) -> str:
    """Generate deterministic SHA-256 hash from error details."""
    norm_trace = "\n".join(line.strip() for line in (stack_trace or "").splitlines() if line.strip())
    raw = f"{service_name}:{message}:{norm_trace}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_rca(signature_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve RCA payload from cache (memory or Redis)."""
    # Fast path: in-memory cache
    if signature_hash in _MEMORY_CACHE:
        return _MEMORY_CACHE[signature_hash]
    return None


def set_cached_rca(signature_hash: str, rca_data: Dict[str, Any]) -> None:
    """Store RCA payload in cache."""
    _MEMORY_CACHE[signature_hash] = rca_data