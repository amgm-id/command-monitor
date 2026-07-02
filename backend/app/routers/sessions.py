from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.session_log import SessionLog, ActiveSession, SessionStatus
from app.models.server import Server
from app.models.server_action import ServerAction, ActionStatus
from app.models.user import User
from app.schemas.session_log import SessionLogResponse, ActiveSessionResponse
from app.utils.security import get_current_user
from app.utils.export import export_csv, export_excel, export_pdf


class KillSessionRequest(BaseModel):
    server_id: UUID
    terminal: Optional[str] = None
    pid: Optional[int] = None
    username: Optional[str] = None

router = APIRouter(prefix="/sessions", tags=["Sessions"])

SESSION_FIELDS = ["login_time", "logout_time", "duration", "server_name", "username",
                  "remote_ip", "terminal", "login_method", "status"]


@router.post("/kill")
def kill_session(
    req: KillSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = db.query(Server).filter(Server.id == req.server_id, Server.is_active == True).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server tidak ditemukan")
    if not req.terminal and not req.pid:
        raise HTTPException(status_code=400, detail="Butuh terminal atau pid")

    action = ServerAction(
        server_id=req.server_id,
        action_type="kill_session",
        payload={
            "terminal": req.terminal,
            "pid": req.pid,
            "username": req.username,
        },
        status=ActionStatus.PENDING,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {"action_id": action.id, "status": "pending", "message": f"Perintah kill dikirim ke {server.name}"}


@router.get("/action/{action_id}/status")
def get_action_status(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = db.query(ServerAction).filter(ServerAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action tidak ditemukan")
    return {"id": action.id, "status": action.status, "result": action.result, "executed_at": action.executed_at}


@router.get("/active", response_model=List[dict])
def list_active_sessions(
    server_id: Optional[UUID] = Query(None),
    username: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ActiveSession, Server).outerjoin(Server, ActiveSession.server_id == Server.id)
    if server_id:
        q = q.filter(ActiveSession.server_id == server_id)
    if username:
        q = q.filter(ActiveSession.username.ilike(f"%{username}%"))

    results = []
    for session, server in q.order_by(desc(ActiveSession.login_time)).all():
        data = ActiveSessionResponse.model_validate(session).model_dump()
        data["server_name"] = server.name if server else None
        data["server_ip"] = server.ip_address if server else None
        results.append(data)
    return results


@router.get("/history", response_model=dict)
def list_session_history(
    username: Optional[str] = Query(None),
    remote_ip: Optional[str] = Query(None),
    server_id: Optional[UUID] = Query(None),
    status: Optional[SessionStatus] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SessionLog, Server).outerjoin(Server, SessionLog.server_id == Server.id)
    if username:
        q = q.filter(SessionLog.username.ilike(f"%{username}%"))
    if remote_ip:
        q = q.filter(SessionLog.remote_ip.ilike(f"%{remote_ip}%"))
    if server_id:
        q = q.filter(SessionLog.server_id == server_id)
    if status:
        q = q.filter(SessionLog.status == status)
    if date_from:
        q = q.filter(SessionLog.login_time >= date_from)
    if date_to:
        q = q.filter(SessionLog.login_time <= date_to)

    q = q.order_by(desc(SessionLog.login_time))
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for log, server in rows:
        data = SessionLogResponse.model_validate(log).model_dump()
        data["server_name"] = server.name if server else None
        items.append(data)

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/history/export/{format}")
def export_sessions(
    format: str,
    username: Optional[str] = Query(None),
    server_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SessionLog, Server).outerjoin(Server, SessionLog.server_id == Server.id)
    if username:
        q = q.filter(SessionLog.username.ilike(f"%{username}%"))
    if server_id:
        q = q.filter(SessionLog.server_id == server_id)
    if date_from:
        q = q.filter(SessionLog.login_time >= date_from)
    if date_to:
        q = q.filter(SessionLog.login_time <= date_to)

    rows = q.order_by(desc(SessionLog.login_time)).limit(10000).all()
    data = []
    for log, server in rows:
        data.append({
            "login_time": log.login_time,
            "logout_time": log.logout_time or "",
            "duration": f"{log.duration}s" if log.duration else "",
            "server_name": server.name if server else "",
            "username": log.username,
            "remote_ip": log.remote_ip or "",
            "terminal": log.terminal or "",
            "login_method": log.login_method.value,
            "status": log.status.value,
        })

    title = "Login History Report"
    if format == "csv":
        return Response(export_csv(data, SESSION_FIELDS), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=login_history.csv"})
    elif format == "excel":
        return Response(export_excel(data, SESSION_FIELDS, "Login History"),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=login_history.xlsx"})
    elif format == "pdf":
        return Response(export_pdf(data, SESSION_FIELDS, title), media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=login_history.pdf"})
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Format must be csv, excel, or pdf")
