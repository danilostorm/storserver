import json
import os
import socket
from pathlib import Path

import docker
from docker.errors import DockerException, NotFound
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

AGENT_TOKEN = os.environ.get("AGENT_SHARED_TOKEN", "")
PUBLIC_HOST = os.environ.get("AGENT_PUBLIC_HOST", "127.0.0.1")
TEMPLATES_DIR = Path(os.environ.get("GAME_TEMPLATES_DIR", "/opt/storserver/games"))
STORAGE_DIR = Path(os.environ.get("STORSERVER_STORAGE_DIR", "/var/lib/storserver"))
PORT_MIN = int(os.environ.get("GAME_PORT_MIN", "20000"))
PORT_MAX = int(os.environ.get("GAME_PORT_MAX", "49999"))

app = FastAPI(title="StorServer Agent", version="0.1.0")
client = docker.from_env()


class ServerCreate(BaseModel):
    server_id: int
    name: str
    game_key: str
    cpu_limit: int = Field(default=2, ge=1)
    memory_mb: int = Field(default=2048, ge=512)


def authorize(authorization: str | None = Header(default=None)) -> None:
    if not AGENT_TOKEN:
        raise HTTPException(status_code=503, detail="Agent token is not configured")
    if authorization != f"Bearer {AGENT_TOKEN}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")


def load_template(game_key: str) -> dict:
    path = TEMPLATES_DIR / f"{game_key}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Game template '{game_key}' not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("enabled", False):
        raise HTTPException(status_code=409, detail=f"Game template '{game_key}' is not enabled yet")
    return data


def used_host_ports() -> set[tuple[int, str]]:
    result: set[tuple[int, str]] = set()
    for container in client.containers.list(all=True):
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        for key, bindings in ports.items():
            container_port, protocol = key.split("/", 1)
            for binding in bindings or []:
                if binding.get("HostPort"):
                    result.add((int(binding["HostPort"]), protocol))
    return result


def allocate_port(protocol: str, used: set[tuple[int, str]], preferred: int | None = None) -> int:
    if preferred and (preferred, protocol) not in used:
        used.add((preferred, protocol))
        return preferred
    for port in range(PORT_MIN, PORT_MAX + 1):
        if (port, protocol) not in used:
            used.add((port, protocol))
            return port
    raise HTTPException(status_code=503, detail="No free game ports available on node")


def find_server_container(server_id: int):
    matches = client.containers.list(all=True, filters={"label": f"storserver.server_id={server_id}"})
    if not matches:
        raise HTTPException(status_code=404, detail="Server container not found")
    return matches[0]


def docker_status(container) -> str:
    container.reload()
    return "running" if container.status == "running" else "stopped"


@app.get("/health")
def health() -> dict:
    try:
        client.ping()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail=f"Docker unavailable: {exc}") from exc
    return {"status": "ok", "service": "storserver-agent", "public_host": PUBLIC_HOST}


@app.get("/v1/node", dependencies=[Depends(authorize)])
def node_info() -> dict:
    info = client.info()
    return {
        "status": "ok",
        "hostname": socket.gethostname(),
        "docker_version": client.version().get("Version"),
        "containers": info.get("Containers", 0),
        "containers_running": info.get("ContainersRunning", 0),
        "cpus": info.get("NCPU", 0),
        "memory_bytes": info.get("MemTotal", 0),
    }


@app.post("/v1/servers", dependencies=[Depends(authorize)], status_code=201)
def create_server(payload: ServerCreate) -> dict:
    existing = client.containers.list(all=True, filters={"label": f"storserver.server_id={payload.server_id}"})
    if existing:
        container = existing[0]
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        first_public = None
        for bindings in ports.values():
            if bindings:
                first_public = int(bindings[0]["HostPort"])
                break
        return {
            "container_id": container.id,
            "status": docker_status(container),
            "public_host": PUBLIC_HOST,
            "public_port": first_public,
        }

    template = load_template(payload.game_key)
    used = used_host_ports()
    port_bindings: dict[str, int] = {}
    public_port = None

    for spec in template.get("ports", []):
        protocol = spec.get("protocol", "udp")
        container_port = int(spec["container"])
        host_port = allocate_port(protocol, used, spec.get("preferred_host"))
        port_bindings[f"{container_port}/{protocol}"] = host_port
        if spec.get("role") == "game" and public_port is None:
            public_port = host_port

    server_dir = STORAGE_DIR / "servers" / str(payload.server_id)
    server_dir.mkdir(parents=True, exist_ok=True)
    volumes = {}
    for volume in template.get("volumes", []):
        host_dir = server_dir / volume.get("host_subdir", "data")
        host_dir.mkdir(parents=True, exist_ok=True)
        volumes[str(host_dir)] = {"bind": volume["container"], "mode": volume.get("mode", "rw")}

    environment = {str(k): str(v) for k, v in template.get("environment", {}).items()}
    environment.update(
        {
            "STORSERVER_SERVER_ID": str(payload.server_id),
            "STORSERVER_SERVER_NAME": payload.name,
        }
    )

    try:
        container = client.containers.run(
            template["image"],
            command=template.get("command"),
            name=f"storserver-{payload.server_id}",
            detach=True,
            restart_policy={"Name": "unless-stopped"},
            labels={
                "storserver.managed": "true",
                "storserver.server_id": str(payload.server_id),
                "storserver.game_key": payload.game_key,
            },
            environment=environment,
            ports=port_bindings,
            volumes=volumes,
            mem_limit=f"{payload.memory_mb}m",
            nano_cpus=payload.cpu_limit * 1_000_000_000,
        )
    except DockerException as exc:
        raise HTTPException(status_code=500, detail=f"Docker provisioning failed: {exc}") from exc

    return {
        "container_id": container.id,
        "status": docker_status(container),
        "public_host": PUBLIC_HOST,
        "public_port": public_port,
    }


@app.post("/v1/servers/{server_id}/start", dependencies=[Depends(authorize)])
def start_server(server_id: int) -> dict:
    container = find_server_container(server_id)
    container.start()
    return {"status": docker_status(container)}


@app.post("/v1/servers/{server_id}/stop", dependencies=[Depends(authorize)])
def stop_server(server_id: int) -> dict:
    container = find_server_container(server_id)
    container.stop(timeout=20)
    return {"status": docker_status(container)}


@app.post("/v1/servers/{server_id}/restart", dependencies=[Depends(authorize)])
def restart_server(server_id: int) -> dict:
    container = find_server_container(server_id)
    container.restart(timeout=20)
    return {"status": docker_status(container)}


@app.get("/v1/servers/{server_id}/logs", dependencies=[Depends(authorize)])
def server_logs(server_id: int, tail: int = 200) -> dict:
    container = find_server_container(server_id)
    tail = max(1, min(tail, 2000))
    return {"logs": container.logs(tail=tail).decode("utf-8", errors="replace")}


@app.delete("/v1/servers/{server_id}", dependencies=[Depends(authorize)])
def delete_server(server_id: int) -> dict:
    container = find_server_container(server_id)
    try:
        container.remove(force=True)
    except NotFound:
        pass
    return {"status": "deleted"}
