from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Text, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class ServerAction(Base):
    __tablename__ = "server_actions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)   # "kill_session"
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(Enum(ActionStatus), default=ActionStatus.PENDING, index=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    executed_at = Column(DateTime, nullable=True)

    server = relationship("Server")
