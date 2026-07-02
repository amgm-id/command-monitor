from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from app.database import get_db
from app.models.command_log import CommandLog, RiskLevel
from app.models.session_log import SessionLog, ActiveSession
from app.models.alert import Alert
from app.models.server import Server
from app.models.user import User
from app.utils.security import get_current_user
from app.utils.timezone import utc_now

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _wita_day_bounds():
    """Kembalikan (start_of_today, now) — waktu lokal WITA."""
    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, now


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today_start, now = _wita_day_bounds()
    week_start = today_start - timedelta(days=7)

    total_commands_today = db.query(func.count(CommandLog.id)).filter(
        CommandLog.timestamp >= today_start
    ).scalar() or 0

    total_commands_week = db.query(func.count(CommandLog.id)).filter(
        CommandLog.timestamp >= week_start
    ).scalar() or 0

    active_sessions_count = db.query(func.count(ActiveSession.id)).scalar() or 0

    unacknowledged_alerts = db.query(func.count(Alert.id)).filter(
        Alert.is_acknowledged == False
    ).scalar() or 0

    high_risk_today = db.query(func.count(Alert.id)).filter(
        Alert.timestamp >= today_start,
        Alert.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]),
    ).scalar() or 0

    total_servers = db.query(func.count(Server.id)).filter(Server.is_active == True).scalar() or 0

    online_threshold = now - timedelta(minutes=5)
    online_servers = db.query(func.count(Server.id)).filter(
        Server.is_active == True,
        Server.last_seen >= online_threshold,
    ).scalar() or 0

    top_users = (
        db.query(CommandLog.username, func.count(CommandLog.id).label("count"))
        .filter(CommandLog.timestamp >= today_start)
        .group_by(CommandLog.username)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    top_ips = (
        db.query(CommandLog.remote_ip, func.count(CommandLog.id).label("count"))
        .filter(CommandLog.timestamp >= today_start, CommandLog.remote_ip.isnot(None))
        .group_by(CommandLog.remote_ip)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    top_servers = (
        db.query(Server.name, func.count(CommandLog.id).label("count"))
        .join(CommandLog, CommandLog.server_id == Server.id)
        .filter(CommandLog.timestamp >= today_start)
        .group_by(Server.name)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    recent_commands = (
        db.query(CommandLog, Server)
        .outerjoin(Server, CommandLog.server_id == Server.id)
        .order_by(desc(CommandLog.timestamp))
        .limit(10)
        .all()
    )

    recent_cmd_list = []
    for cmd, server in recent_commands:
        recent_cmd_list.append({
            "id": cmd.id,
            "timestamp": cmd.timestamp.isoformat(),
            "username": cmd.username,
            "command": cmd.command[:120],
            "server_name": server.name if server else "unknown",
            "remote_ip": cmd.remote_ip,
            "risk_level": cmd.risk_level.value,
        })

    return {
        "total_commands_today": total_commands_today,
        "total_commands_week": total_commands_week,
        "active_sessions": active_sessions_count,
        "unacknowledged_alerts": unacknowledged_alerts,
        "high_risk_today": high_risk_today,
        "total_servers": total_servers,
        "online_servers": online_servers,
        "top_users": [{"username": u, "count": c} for u, c in top_users],
        "top_ips": [{"ip": ip or "local", "count": c} for ip, c in top_ips],
        "top_servers": [{"name": n, "count": c} for n, c in top_servers],
        "recent_commands": recent_cmd_list,
    }


@router.get("/activity-chart")
def get_activity_chart(
    period: str = Query("24h", regex="^(24h|7d|30d)$"),
    server_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = utc_now()

    if period == "24h":
        start = now - timedelta(hours=24)
        trunc_unit = "hour"
        def fmt_bucket(dt): return dt.strftime("%Y-%m-%d %H:00")
    elif period == "7d":
        start = now - timedelta(days=7)
        trunc_unit = "day"
        def fmt_bucket(dt): return dt.strftime("%Y-%m-%d")
    else:
        start = now - timedelta(days=30)
        trunc_unit = "day"
        def fmt_bucket(dt): return dt.strftime("%Y-%m-%d")

    q = db.query(
        func.date_trunc(trunc_unit, CommandLog.timestamp).label("bucket"),
        func.count(CommandLog.id).label("count"),
        func.sum(case(
            (CommandLog.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]), 1),
            else_=0
        )).label("high_risk"),
    ).filter(CommandLog.timestamp >= start)

    if server_id:
        q = q.filter(CommandLog.server_id == server_id)

    rows = q.group_by("bucket").order_by("bucket").all()

    return [
        {
            "time": fmt_bucket(row.bucket),
            "total": row.count,
            "high_risk": int(row.high_risk or 0),
        }
        for row in rows
    ]


@router.get("/risk-distribution")
def get_risk_distribution(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = utc_now()
    start = date_from or (now - timedelta(days=7))
    end = date_to or now

    rows = (
        db.query(CommandLog.risk_level, func.count(CommandLog.id).label("count"))
        .filter(CommandLog.timestamp >= start, CommandLog.timestamp <= end)
        .group_by(CommandLog.risk_level)
        .all()
    )
    return [{"risk_level": r.value, "count": c} for r, c in rows]
