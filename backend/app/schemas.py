from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import ServerStatus, UserRole


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    role: UserRole = UserRole.customer


class NodeCreate(BaseModel):
    name: str
    region: str = "unknown"
    agent_url: str
    token: str


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    region: str
    agent_url: str
    enabled: bool


class ServerCreate(BaseModel):
    name: str
    game_key: str
    node_id: int
    cpu_limit: int = Field(default=2, ge=1, le=64)
    memory_mb: int = Field(default=2048, ge=512, le=262144)


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    game_key: str
    status: ServerStatus
    container_id: str | None
    public_host: str | None
    public_port: int | None
    cpu_limit: int
    memory_mb: int
    owner_id: int
    node_id: int
