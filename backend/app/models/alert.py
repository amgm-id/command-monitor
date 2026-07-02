from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.command_log import RiskLevel


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    command_log_id = Column(BigInteger, ForeignKey("command_logs.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=False, index=True)
    remote_ip = Column(String(45), nullable=True)
    command = Column(Text, nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False, index=True)
    risk_reason = Column(Text, nullable=True)
    is_acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)

    server = relationship("Server", back_populates="alerts")
    command_log = relationship("CommandLog", back_populates="alert")
    acknowledged_by_user = relationship("User", back_populates="acknowledged_alerts")
