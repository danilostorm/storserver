from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import AuditLog, GameServer, Node, ServerStatus, User, UserRole
from .schemas import NodeCreate, NodeOut, ServerCreate, ServerOut, TokenOut, UserCreate, UserOut
from .security import create_access_token, get_current_user, hash_password, verify_password


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def audit(db: Session, user_id: int | None, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == settings.admin_email))
        if not admin:
            db.add(
                User(
                    email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password),
                    role=UserRole.admin,
                    is_active=True,
                )
            )

        local_node = db.scalar(select(Node).where(Node.name == settings.node_name))
        if not local_node:
            db.add(
                Node(
                    name=settings.node_name,
                    region=settings.node_region,
                    agent_url=settings.agent_url,
                    token=settings.agent_shared_token,
                    enabled=True,
                )
            )
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "storserver-api"}


@app.post("/api/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    audit(db, user.id, "auth.login")
    db.commit()
    return TokenOut(access_token=create_access_token(user.email))


@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.get("/api/admin/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


@app.post("/api/admin/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit(db, admin.id, "user.create", f"user_id={user.id} email={user.email}")
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/nodes", response_model=list[NodeOut])
def list_nodes(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Node]:
    return list(db.scalars(select(Node).where(Node.enabled.is_(True)).order_by(Node.id)).all())


@app.post("/api/admin/nodes", response_model=NodeOut, status_code=201)
def create_node(payload: NodeCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Node:
    if db.scalar(select(Node).where(Node.name == payload.name)):
        raise HTTPException(status_code=409, detail="Node name already exists")
    node = Node(**payload.model_dump(), enabled=True)
    db.add(node)
    db.flush()
    audit(db, admin.id, "node.create", f"node_id={node.id} name={node.name}")
    db.commit()
    db.refresh(node)
    return node


@app.get("/api/servers", response_model=list[ServerOut])
def list_servers(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GameServer]:
    stmt = select(GameServer).order_by(GameServer.id.desc())
    if user.role != UserRole.admin:
        stmt = stmt.where(GameServer.owner_id == user.id)
    return list(db.scalars(stmt).all())


async def agent_request(node: Node, method: str, path: str, json: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {node.token}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, f"{node.agent_url.rstrip('/')}{path}", headers=headers, json=json)
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Node agent error: {exc}") from exc


@app.post("/api/servers", response_model=ServerOut, status_code=201)
async def create_server(payload: ServerCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GameServer:
    node = db.get(Node, payload.node_id)
    if not node or not node.enabled:
        raise HTTPException(status_code=404, detail="Node not found")

    server = GameServer(
        name=payload.name,
        game_key=payload.game_key,
        node_id=node.id,
        owner_id=user.id,
        cpu_limit=payload.cpu_limit,
        memory_mb=payload.memory_mb,
        status=ServerStatus.provisioning,
    )
    db.add(server)
    db.flush()

    result = await agent_request(
        node,
        "POST",
        "/v1/servers",
        {
            "server_id": server.id,
            "name": server.name,
            "game_key": server.game_key,
            "cpu_limit": server.cpu_limit,
            "memory_mb": server.memory_mb,
        },
    )
    server.container_id = result.get("container_id")
    server.public_host = result.get("public_host")
    server.public_port = result.get("public_port")
    server.status = ServerStatus(result.get("status", "stopped"))
    audit(db, user.id, "server.create", f"server_id={server.id} game={server.game_key}")
    db.commit()
    db.refresh(server)
    return server


async def control_server(server_id: int, action: str, user: User, db: Session) -> GameServer:
    server = db.get(GameServer, server_id)
    if not server or (user.role != UserRole.admin and server.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Server not found")
    node = db.get(Node, server.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    result = await agent_request(node, "POST", f"/v1/servers/{server.id}/{action}")
    if result.get("status"):
        server.status = ServerStatus(result["status"])
    audit(db, user.id, f"server.{action}", f"server_id={server.id}")
    db.commit()
    db.refresh(server)
    return server


@app.post("/api/servers/{server_id}/start", response_model=ServerOut)
async def start_server(server_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GameServer:
    return await control_server(server_id, "start", user, db)


@app.post("/api/servers/{server_id}/stop", response_model=ServerOut)
async def stop_server(server_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GameServer:
    return await control_server(server_id, "stop", user, db)


@app.post("/api/servers/{server_id}/restart", response_model=ServerOut)
async def restart_server(server_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GameServer:
    return await control_server(server_id, "restart", user, db)
