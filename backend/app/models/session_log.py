from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, BigInteger, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class LoginMethod(str, enum.Enum):
    SSH = "ssh"
    CONSOLE = "console"
    SU = "su"
    SUDO = "sudo"
    UNKNOWN = "unknown"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SessionLog(Base):
    __tablename__ = "session_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    remote_ip = Column(String(45), nullable=True, index=True)
    terminal = Column(String(30), nullable=True)
    login_time = Column(DateTime, nullable=False, index=True)
    logout_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    login_method = Column(Enum(LoginMethod), default=LoginMethod.UNKNOWN)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE, index=True)
    failed_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    server = relationship("Server", back_populates="session_logs")
    active_session = relationship("ActiveSession", back_populates="session_log", uselist=False)

    __table_args__ = (
        Index("ix_session_logs_login_time_server", "login_time", "server_id"),
    )


class ActiveSession(Base):
    __tablename__ = "active_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    session_log_id = Column(BigInteger, ForeignKey("session_logs.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=False, index=True)
    remote_ip = Column(String(45), nullable=True)
    terminal = Column(String(30), nullable=True)
    login_time = Column(DateTime, nullable=False)
    idle_time = Column(String(20), nullable=True)
    current_process = Column(Text, nullable=True)
    pid = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    server = relationship("Server", back_populates="active_sessions")
    session_log = relationship("SessionLog", back_populates="active_session")
