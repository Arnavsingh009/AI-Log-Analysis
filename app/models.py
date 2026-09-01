from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class LogPayload(BaseModel):
    service_name: str
    level: str = Field(..., description="INFO, WARNING, ERROR, CRITICAL")
    message: str
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)