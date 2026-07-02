import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False)
    agent_token = Column(String(128), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, nullable=True)
    os_info = Column(JSON, nullable=True)
    agent_version = Column(String(20), nullable=True)
    total_commands = Column(Integer, default=0)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    command_logs = relationship("CommandLog", back_populates="server", lazy="dynamic")
    session_logs = relationship("SessionLog", back_populates="server", lazy="dynamic")
    active_sessions = relationship("ActiveSession", back_populates="server", lazy="dynamic")
    alerts = relationship("Alert", back_populates="server", lazy="dynamic")
