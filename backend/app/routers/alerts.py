from typing import Optional
from uuid import UUID
from datetime import datetime
from app.utils.timezone import utc_now
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.alert import Alert
from app.models.server import Server
from app.models.user import User
from app.models.command_log import RiskLevel
from app.schemas.alert import AlertResponse, AlertAcknowledge
from app.utils.security import get_current_user, require_auditor_plus
from app.services.audit_service import log_action

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=dict)
def list_alerts(
    server_id: Optional[UUID] = Query(None),
    username: Optional[str] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None),
    is_acknowledged: Optional[bool] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Alert, Server).outerjoin(Server, Alert.server_id == Server.id)
    if server_id:
        q = q.filter(Alert.server_id == server_id)
    if username:
        q = q.filter(Alert.username.ilike(f"%{username}%"))
    if risk_level:
        q = q.filter(Alert.risk_level == risk_level)
    if is_acknowledged is not None:
        q = q.filter(Alert.is_acknowledged == is_acknowledged)
    if date_from:
        q = q.filter(Alert.timestamp >= date_from)
    if date_to:
        q = q.filter(Alert.timestamp <= date_to)

    q = q.order_by(desc(Alert.timestamp))
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for alert, server in rows:
        data = AlertResponse.model_validate(alert).model_dump()
        data["server_name"] = server.name if server else None
        if alert.acknowledged_by_user:
            data["acknowledged_by"] = alert.acknowledged_by_user.username
        items.append(data)

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(Alert).filter(Alert.is_acknowledged == False).count()
    return {"count": count}


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor_plus),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_by_id = current_user.id
    alert.acknowledged_at = utc_now()
    db.commit()

    log_action(db, current_user, "ALERT_ACKNOWLEDGED", "alert", str(alert_id),
               {"note": body.note, "command": alert.command})
    return {"message": "Alert acknowledged"}


@router.post("/acknowledge-bulk")
def acknowledge_bulk(
    alert_ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor_plus),
):
    now = utc_now()
    db.query(Alert).filter(Alert.id.in_(alert_ids), Alert.is_acknowledged == False).update(
        {"is_acknowledged": True, "acknowledged_by_id": current_user.id, "acknowledged_at": now},
        synchronize_session=False,
    )
    db.commit()
    log_action(db, current_user, "ALERTS_BULK_ACKNOWLEDGED", details={"count": len(alert_ids)})
    return {"message": f"{len(alert_ids)} alerts acknowledged"}
