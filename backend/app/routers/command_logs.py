from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.command_log import CommandLog, RiskLevel
from app.models.server import Server
from app.models.user import User
from app.schemas.command_log import CommandLogResponse
from app.utils.security import get_current_user
from app.utils.export import export_csv, export_excel, export_pdf

router = APIRouter(prefix="/command-logs", tags=["Command Logs"])

COMMAND_LOG_FIELDS = ["timestamp", "server_name", "server_ip", "username", "remote_ip",
                      "terminal", "working_dir", "command", "exit_code", "risk_level", "risk_reason"]


def _build_query(db, username, remote_ip, command, server_id, risk_level, date_from, date_to):
    q = db.query(CommandLog, Server).outerjoin(Server, CommandLog.server_id == Server.id)
    if username:
        q = q.filter(CommandLog.username.ilike(f"%{username}%"))
    if remote_ip:
        q = q.filter(CommandLog.remote_ip.ilike(f"%{remote_ip}%"))
    if command:
        q = q.filter(CommandLog.command.ilike(f"%{command}%"))
    if server_id:
        q = q.filter(CommandLog.server_id == server_id)
    if risk_level:
        q = q.filter(CommandLog.risk_level == risk_level)
    if date_from:
        q = q.filter(CommandLog.timestamp >= date_from)
    if date_to:
        q = q.filter(CommandLog.timestamp <= date_to)
    return q.order_by(desc(CommandLog.timestamp))


@router.get("/", response_model=dict)
def list_command_logs(
    username: Optional[str] = Query(None),
    remote_ip: Optional[str] = Query(None),
    command: Optional[str] = Query(None),
    server_id: Optional[UUID] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _build_query(db, username, remote_ip, command, server_id, risk_level, date_from, date_to)
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for log, server in rows:
        data = CommandLogResponse.model_validate(log)
        data.server_name = server.name if server else None
        data.server_ip = server.ip_address if server else None
        items.append(data.model_dump())

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/export/{format}")
def export_command_logs(
    format: str,
    username: Optional[str] = Query(None),
    remote_ip: Optional[str] = Query(None),
    command: Optional[str] = Query(None),
    server_id: Optional[UUID] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _build_query(db, username, remote_ip, command, server_id, risk_level, date_from, date_to)
    rows = q.limit(10000).all()

    data = []
    for log, server in rows:
        data.append({
            "timestamp": log.timestamp,
            "server_name": server.name if server else "",
            "server_ip": server.ip_address if server else "",
            "username": log.username,
            "remote_ip": log.remote_ip or "",
            "terminal": log.terminal or "",
            "working_dir": log.working_dir or "",
            "command": log.command,
            "exit_code": log.exit_code if log.exit_code is not None else "",
            "risk_level": log.risk_level.value,
            "risk_reason": log.risk_reason or "",
        })

    title = "Command History Report"
    if format == "csv":
        content = export_csv(data, COMMAND_LOG_FIELDS)
        return Response(content=content, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=command_history.csv"})
    elif format == "excel":
        content = export_excel(data, COMMAND_LOG_FIELDS, "Command History")
        return Response(content=content,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=command_history.xlsx"})
    elif format == "pdf":
        content = export_pdf(data, COMMAND_LOG_FIELDS, title)
        return Response(content=content, media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=command_history.pdf"})
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Format must be csv, excel, or pdf")
