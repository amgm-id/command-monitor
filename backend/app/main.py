from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import engine, Base, SessionLocal
from app.models import User, Server, CommandLog, SessionLog, ActiveSession, Alert, AuditTrail, ServerAction
from app.utils.security import hash_password
from app.models.user import UserRole

# Import routers
from app.routers import auth, users, servers, command_logs, sessions, alerts, dashboard, agent, websocket as ws_router

settings = get_settings()


def create_tables():
    Base.metadata.create_all(bind=engine)


def seed_default_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            admin = User(
                username="admin",
                email="admin@serveragent.local",
                password_hash=hash_password("Admin@1234"),
                full_name="Super Administrator",
                role=UserRole.SUPER_ADMIN,
            )
            db.add(admin)
            db.commit()
            print("✅ Default admin created: admin / Admin@1234")
    except IntegrityError:
        # Another worker already inserted the admin (multi-worker race condition)
        db.rollback()
    except Exception as e:
        db.rollback()
        print(f"[WARN] seed_default_admin: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    seed_default_admin()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(servers.router, prefix="/api")
app.include_router(command_logs.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(ws_router.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
