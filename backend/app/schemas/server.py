from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel


class ServerCreate(BaseModel):
    name: str
    hostname: str
    ip_address: str
    description: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServerResponse(BaseModel):
    id: UUID
    name: str
    hostname: str
    ip_address: str
    agent_token: str
    is_active: bool
    last_seen: Optional[datetime] = None
    os_info: Optional[Any] = None
    agent_version: Optional[str] = None
    total_commands: int
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServerStats(BaseModel):
    server_id: UUID
    server_name: str
    total_commands_today: int
    total_commands_week: int
    active_sessions: int
    high_risk_alerts: int
    last_seen: Optional[datetime] = None
    is_online: bool
