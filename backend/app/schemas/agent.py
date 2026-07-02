from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel
from app.schemas.command_log import CommandLogCreate
from app.schemas.session_log import SessionLogCreate, ActiveSessionUpdate


class AgentHeartbeat(BaseModel):
    hostname: str
    ip_address: str
    os_info: Optional[Any] = None
    agent_version: Optional[str] = None
    uptime: Optional[float] = None
    load_avg: Optional[List[float]] = None
    timestamp: datetime


class AgentCommandBatch(BaseModel):
    commands: List[CommandLogCreate]


class AgentSessionBatch(BaseModel):
    sessions: List[SessionLogCreate]
    active_sessions: List[ActiveSessionUpdate]
