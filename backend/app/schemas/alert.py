from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.models.command_log import RiskLevel


class AlertResponse(BaseModel):
    id: int
    server_id: Optional[UUID] = None
    server_name: Optional[str] = None
    command_log_id: Optional[int] = None
    username: str
    remote_ip: Optional[str] = None
    command: str
    risk_level: RiskLevel
    risk_reason: Optional[str] = None
    is_acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertAcknowledge(BaseModel):
    note: Optional[str] = None
