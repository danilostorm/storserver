# StorServer roadmap

## Milestone 0.1 — platform foundation

- [x] Repository bootstrap
- [x] Docker Compose development stack
- [x] PostgreSQL and Redis
- [x] FastAPI control plane
- [x] JWT login and admin bootstrap
- [x] Customer/server/node data model
- [x] Initial React panel
- [x] Docker node agent
- [x] Game-template schema
- [x] Integration tests
- [x] Migrations with Alembic
- [x] Server deletion and log UI
- [x] Per-node health/status polling

## Milestone 0.2 — first production-quality game runtime

Target: Counter-Strike 1.6 first because the networking model is relatively simple and it is already known to work in the current infrastructure.

- StorServer-owned runtime image
- SteamCMD install/update lifecycle
- port allocation validation
- public query visibility test
- RCON support
- server.cfg editor
- backups
- console streaming
- customer limits

Then:
- Killing Floor 2
- Euro Truck Simulator 2
- American Truck Simulator
- Terraria
- Minecraft

## Milestone 0.3 — multi-node hosting

- secure node enrollment
- per-node API keys
- mTLS/tunnel
- resource scheduler
- node drain/maintenance mode
- node labels and regions
- automatic port reservation
- provider-specific cloud firewall integration

## Milestone 0.4 — customer hosting product

- plans and quotas
- order provisioning API
- suspension/unsuspension
- invoices/payment-provider abstraction
- support/operator roles
- email notifications
- customer API keys

## Milestone 0.5 — game websites

- wildcard `*.hoststorm.cloud`
- per-server slug reservation
- automatically generated site
- status/players/map widgets
- themes and branding
- Discord/community links
- optional custom domains
- TLS automation

## Milestone 1.0

Production launch criteria:
- tested backup/restore
- audit trail
- disaster-recovery documentation
- agent credential rotation
- 2FA
- rate limiting
- production database migrations
- monitoring and alerting
- load/capacity tests
- security review
