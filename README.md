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

## First install

From the cloned repository:

```bash
bash ./install.sh
```

The installer creates `.env` automatically when it does not exist, generates random JWT/database/agent/admin secrets, validates Docker Compose, builds the images and starts the stack.

It prints the generated admin credentials at the end. The `.env` file is ignored by Git and is never committed.

Default local endpoints:

- Panel: `http://SERVER-IP:3000`
- API docs: `http://SERVER-IP:8000/docs`

## Updating

After the first install, normal updates are:

```bash
bash ./update.sh
```

This performs a fast-forward pull from `origin/main` and then rebuilds/restarts the StorServer stack while preserving the existing `.env` and persistent Docker volumes.

## Manual development start

If you prefer to manage environment variables manually:

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
```

## Project status

Initial platform foundation. The current milestone focuses on authentication, users, nodes, server inventory, a local agent, health checks and the first game catalog.

## Repository layout

```text
backend/    FastAPI control plane
frontend/   React/Vite web panel
agent/      Remote Docker node agent
games/      Game template catalog
docs/       Architecture and deployment notes
install.sh  First-install/bootstrap helper
update.sh   Update + rebuild helper
```

## Security note

Do not expose the Docker daemon TCP API publicly. The agent talks to the local Docker socket and authenticates incoming control-plane requests with a node token.
