from sqlalchemy.orm import Session
from app.models.audit_trail import AuditTrail
from app.models.user import User
from typing import Optional, Any


def log_action(
    db: Session,
    user: Optional[User],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Any] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditTrail:
    trail = AuditTrail(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(trail)
    db.commit()
    return trail
