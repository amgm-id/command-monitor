from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from app.models.session_log import LoginMethod, SessionStatus


class SessionLogCreate(BaseModel):
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    login_time: datetime
    login_method: LoginMethod = LoginMethod.UNKNOWN
    status: SessionStatus = SessionStatus.ACTIVE
    failed_reason: Optional[str] = None


class SessionLogResponse(BaseModel):
    id: int
    server_id: Optional[UUID] = None
    server_name: Optional[str] = None
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    login_time: datetime
    logout_time: Optional[datetime] = None
    duration: Optional[int] = None
    login_method: LoginMethod
    status: SessionStatus
    failed_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActiveSessionUpdate(BaseModel):
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    login_time: datetime
    idle_time: Optional[str] = None
    current_process: Optional[str] = None
    pid: Optional[int] = None


class ActiveSessionResponse(BaseModel):
    id: int
    server_id: UUID
    server_name: Optional[str] = None
    server_ip: Optional[str] = None
    username: str
    remote_ip: Optional[str] = None
    terminal: Optional[str] = None
    login_time: datetime
    idle_time: Optional[str] = None
    current_process: Optional[str] = None
    pid: Optional[int] = None
    updated_at: datetime

    model_config = {"from_attributes": True}
