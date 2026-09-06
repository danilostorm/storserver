# StorServer

StorServer is a self-hosted game hosting control plane designed for commercial use.

It provides:
- Admin and customer panels
- Multi-node game server orchestration
- Docker-based isolation
- PostgreSQL persistence and Redis queues
- Agent-based remote node management
- Game templates (Killing Floor 2, Counter-Strike, ETS2, ATS and more)
- Public game websites and wildcard subdomain support for `*.hoststorm.cloud`
- Resource limits, audit logs, backups and future billing integration

## Architecture

```text
Browser
  |
  v
StorServer Frontend
  |
  v
StorServer API / Control Plane
  |                 \
  |                  \--> PostgreSQL / Redis
  v
StorServer Agent(s)
  |
  v
Docker game containers
```

The controller never needs direct access to remote Docker sockets. Each node runs a StorServer Agent that performs authorized actions locally.

## Development quick start

1. Copy `.env.example` to `.env`.
2. Set a strong `JWT_SECRET`, `ADMIN_PASSWORD` and `AGENT_SHARED_TOKEN`.
3. Start the stack:

```bash
docker compose up -d --build
```

4. Open the frontend on port `3000` and the API docs on port `8000/docs`.

## Project status

Initial platform foundation. The current milestone focuses on authentication, users, nodes, server inventory, a local agent, health checks and the first game catalog.

## Repository layout

```text
backend/   FastAPI control plane
frontend/  React/Vite web panel
agent/     Remote Docker node agent
games/     Game template catalog
docs/      Architecture and deployment notes
```

## Security note

Do not expose the Docker daemon TCP API publicly. The agent talks to the local Docker socket and authenticates incoming control-plane requests with a node token.
