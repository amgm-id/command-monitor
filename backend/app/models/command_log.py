from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandLog(Base):
    __tablename__ = "command_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    remote_ip = Column(String(45), nullable=True, index=True)
    terminal = Column(String(30), nullable=True)
    working_dir = Column(String(500), nullable=True)
    command = Column(Text, nullable=False)
    exit_code = Column(Integer, nullable=True)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW, index=True)
    risk_reason = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)

    server = relationship("Server", back_populates="command_logs")
    alert = relationship("Alert", back_populates="command_log", uselist=False)

    __table_args__ = (
        Index("ix_command_logs_timestamp_server", "timestamp", "server_id"),
        Index("ix_command_logs_username_timestamp", "username", "timestamp"),
    )
