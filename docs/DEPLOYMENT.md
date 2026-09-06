# Development deployment

This document describes the first lab deployment on the `storserver` Ubuntu VM.

## Requirements

- Ubuntu Server 24.04 LTS or newer
- Docker Engine with Compose plugin
- Git
- at least 8 GB RAM for development; 16+ GB recommended

## Install

```bash
cd /opt/storserver/storserver
git pull --ff-only origin main
cp .env.example .env
nano .env
```

Set strong values for:

- `JWT_SECRET`
- `ADMIN_PASSWORD`
- `POSTGRES_PASSWORD`
- `DATABASE_URL` (must contain the same Postgres password)
- `AGENT_SHARED_TOKEN`
- `AGENT_PUBLIC_HOST`

Then:

```bash
docker compose up -d --build
```

Check:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:9000/health
```

Panel: `http://VM_IP:3000`

API docs: `http://VM_IP:8000/docs`

## Important

The compose file includes a local agent for lab/development. The agent mounts `/var/run/docker.sock`, which gives it root-equivalent control of Docker. Do not expose port 9000 to the public Internet.

Production nodes will use dedicated node enrollment, network restrictions and encrypted per-node credentials.

## Domain plan

Later production ingress will use:

- `panel.hoststorm.cloud` — control panel
- `api.hoststorm.cloud` — API (optional; can remain same origin)
- `*.hoststorm.cloud` — public game websites

Do not point the wildcard at the development VM until the public-site routing and certificate automation milestone is complete.
