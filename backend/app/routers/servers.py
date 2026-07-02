from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.server import Server
from app.models.user import User
from app.schemas.server import ServerCreate, ServerUpdate, ServerResponse
from app.utils.security import generate_agent_token, get_current_user, require_admin, get_client_ip
from app.services.audit_service import log_action

router = APIRouter(prefix="/servers", tags=["Servers"])


@router.get("/", response_model=List[ServerResponse])
def list_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Server).order_by(Server.created_at.desc()).all()


@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(
    server_data: ServerCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = Server(
        name=server_data.name,
        hostname=server_data.hostname,
        ip_address=server_data.ip_address,
        description=server_data.description,
        agent_token=generate_agent_token(),
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    log_action(db, current_user, "SERVER_CREATED", "server", str(server.id),
               {"name": server.name, "hostname": server.hostname}, get_client_ip(request))
    return server


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(
    server_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(
    server_id: UUID,
    server_data: ServerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    for field, value in server_data.model_dump(exclude_none=True).items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)
    log_action(db, current_user, "SERVER_UPDATED", "server", str(server_id),
               server_data.model_dump(exclude_none=True), get_client_ip(request))
    return server


@router.post("/{server_id}/rotate-token", response_model=ServerResponse)
def rotate_agent_token(
    server_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.agent_token = generate_agent_token()
    db.commit()
    db.refresh(server)

    log_action(db, current_user, "AGENT_TOKEN_ROTATED", "server", str(server_id),
               {"server_name": server.name}, get_client_ip(request))
    return server


@router.delete("/{server_id}")
def delete_server(
    server_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server_name = server.name
    server.is_active = False
    db.commit()

    log_action(db, current_user, "SERVER_DEACTIVATED", "server", str(server_id),
               {"name": server_name}, get_client_ip(request))
    return {"message": f"Server {server_name} deactivated"}
