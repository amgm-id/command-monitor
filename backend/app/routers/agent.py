"""Agent data ingestion endpoints — authenticated by agent token, not JWT."""
from datetime import datetime
from app.utils.timezone import utc_now
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.server import Server
from app.models.command_log import CommandLog
from app.models.session_log import SessionLog, ActiveSession
from app.models.alert import Alert
from app.models.server_action import ServerAction, ActionStatus
from app.schemas.agent import AgentHeartbeat, AgentCommandBatch, AgentSessionBatch
from app.services.risk_detector import detect_risk, is_alert_worthy


class ActionResult(BaseModel):
    result: str
    success: bool = True

router = APIRouter(prefix="/agent", tags=["Agent"])


def get_server_by_token(x_agent_token: str = Header(...), db: Session = Depends(get_db)) -> Server:
    server = db.query(Server).filter(
        Server.agent_token == x_agent_token,
        Server.is_active == True,
    ).first()
    if not server:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")
    return server


async def _broadcast_safe(event_type: str, data: dict):
    """Broadcast to WebSocket clients, ignoring errors (e.g. no clients connected)."""
    try:
        from app.routers.websocket import broadcast
        await broadcast(event_type, data)
    except Exception:
        pass


@router.post("/heartbeat")
async def heartbeat(
    data: AgentHeartbeat,
    server: Server = Depends(get_server_by_token),
    db: Session = Depends(get_db),
):
    server.last_seen = utc_now()
    server.hostname = data.hostname
    if data.ip_address:
        server.ip_address = data.ip_address
    if data.os_info:
        server.os_info = data.os_info
    if data.agent_version:
        server.agent_version = data.agent_version
    db.commit()

    await _broadcast_safe("server_heartbeat", {
        "server_id": str(server.id),
        "server_name": server.name,
        "ip_address": server.ip_address,
        "last_seen": utc_now().isoformat(),
    })

    return {"status": "ok", "server_id": str(server.id), "server_name": server.name}


@router.post("/commands")
async def ingest_commands(
    batch: AgentCommandBatch,
    server: Server = Depends(get_server_by_token),
    db: Session = Depends(get_db),
):
    if not batch.commands:
        return {"ingested": 0}

    new_commands: List[CommandLog] = []
    new_alerts: List[Alert] = []

    for cmd_data in batch.commands:
        risk_level, risk_reason = detect_risk(cmd_data.command)

        cmd_log = CommandLog(
            server_id=server.id,
            username=cmd_data.username,
            remote_ip=cmd_data.remote_ip,
            terminal=cmd_data.terminal,
            working_dir=cmd_data.working_dir,
            command=cmd_data.command,
            exit_code=cmd_data.exit_code,
            session_id=cmd_data.session_id,
            risk_level=risk_level,
            risk_reason=risk_reason if risk_reason else None,
            timestamp=cmd_data.timestamp,
        )
        new_commands.append(cmd_log)

    db.add_all(new_commands)
    db.flush()

    for cmd_log in new_commands:
        if is_alert_worthy(cmd_log.risk_level):
            alert = Alert(
                server_id=server.id,
                command_log_id=cmd_log.id,
                username=cmd_log.username,
                remote_ip=cmd_log.remote_ip,
                command=cmd_log.command,
                risk_level=cmd_log.risk_level,
                risk_reason=cmd_log.risk_reason,
                timestamp=cmd_log.timestamp,
            )
            new_alerts.append(alert)

    if new_alerts:
        db.add_all(new_alerts)

    server.total_commands = (server.total_commands or 0) + len(new_commands)
    server.last_seen = utc_now()
    db.commit()

    # Broadcast to all connected WebSocket clients
    recent = new_commands[-1] if new_commands else None
    await _broadcast_safe("new_commands", {
        "server_name": server.name,
        "count": len(new_commands),
        "alerts": len(new_alerts),
        "latest": {
            "username": recent.username,
            "command": recent.command[:100],
            "risk_level": recent.risk_level.value,
            "timestamp": recent.timestamp.isoformat(),
        } if recent else None,
    })

    if new_alerts:
        await _broadcast_safe("new_alerts", {
            "count": len(new_alerts),
            "server_name": server.name,
        })

    return {"ingested": len(new_commands), "alerts_created": len(new_alerts)}


@router.post("/sessions")
async def ingest_sessions(
    batch: AgentSessionBatch,
    server: Server = Depends(get_server_by_token),
    db: Session = Depends(get_db),
):
    for sess_data in batch.sessions:
        from sqlalchemy import func
        # Dedup: cocokkan dalam window ±1 menit dari login_time (toleransi parsing)
        existing = db.query(SessionLog).filter(
            SessionLog.server_id == server.id,
            SessionLog.username == sess_data.username,
            SessionLog.terminal == sess_data.terminal,
            func.date_trunc('minute', SessionLog.login_time) ==
            func.date_trunc('minute', sess_data.login_time),
        ).first()
        if not existing:
            session_log = SessionLog(
                server_id=server.id,
                username=sess_data.username,
                remote_ip=sess_data.remote_ip,
                terminal=sess_data.terminal,
                login_time=sess_data.login_time,
                login_method=sess_data.login_method,
                status=sess_data.status,
                failed_reason=sess_data.failed_reason,
            )
            db.add(session_log)

    db.query(ActiveSession).filter(ActiveSession.server_id == server.id).delete()

    for active_data in batch.active_sessions:
        active = ActiveSession(
            server_id=server.id,
            username=active_data.username,
            remote_ip=active_data.remote_ip,
            terminal=active_data.terminal,
            login_time=active_data.login_time,
            idle_time=active_data.idle_time,
            current_process=active_data.current_process,
            pid=active_data.pid,
        )
        db.add(active)

    server.last_seen = utc_now()
    db.commit()

    await _broadcast_safe("sessions_updated", {
        "server_name": server.name,
        "active_count": len(batch.active_sessions),
    })

    return {"sessions_ingested": len(batch.sessions), "active_sessions": len(batch.active_sessions)}


@router.get("/actions")
def get_pending_actions(
    server: Server = Depends(get_server_by_token),
    db: Session = Depends(get_db),
):
    """Agent polling: ambil aksi pending untuk server ini."""
    actions = db.query(ServerAction).filter(
        ServerAction.server_id == server.id,
        ServerAction.status == ActionStatus.PENDING,
    ).order_by(ServerAction.id).limit(10).all()

    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "payload": a.payload,
        }
        for a in actions
    ]


@router.post("/actions/{action_id}/result")
def report_action_result(
    action_id: int,
    result: ActionResult,
    server: Server = Depends(get_server_by_token),
    db: Session = Depends(get_db),
):
    """Agent melaporkan hasil eksekusi aksi."""
    action = db.query(ServerAction).filter(
        ServerAction.id == action_id,
        ServerAction.server_id == server.id,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action tidak ditemukan")

    action.status = ActionStatus.DONE if result.success else ActionStatus.FAILED
    action.result = result.result
    action.executed_at = utc_now()
    db.commit()
    return {"ok": True}
