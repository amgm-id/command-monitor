from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.models.command_log import RiskLevel


class CommandLogCreate(BaseModel):
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    working_dir: Optional[str] = None
    command: str
    exit_code: Optional[int] = None
    session_id: Optional[str] = None
    timestamp: datetime


class CommandLogResponse(BaseModel):
    id: int
    server_id: Optional[UUID] = None
    server_name: Optional[str] = None
    server_ip: Optional[str] = None
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    working_dir: Optional[str] = None
    command: str
    exit_code: Optional[int] = None
    risk_level: RiskLevel
    risk_reason: Optional[str] = None
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CommandLogFilter(BaseModel):
    username: Optional[str] = None
    remote_ip: Optional[str] = None
    command: Optional[str] = None
    server_id: Optional[UUID] = None
    risk_level: Optional[RiskLevel] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = 1
    per_page: int = 50
