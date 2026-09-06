# StorServer architecture

## Goals

StorServer is designed as a commercial multi-tenant game-hosting platform, not as a single-host Docker dashboard.

Core principles:

1. Control plane and game nodes are separated.
2. Remote Docker sockets are never exposed to the controller.
3. Every server belongs to a customer and a node.
4. Node resources and port allocations are enforced centrally and locally.
5. Game support is template-driven and versioned.
6. Public game websites are isolated from the control panel.
7. Auditability, quotas and billing hooks are first-class concerns.

## Components

### Control plane

The controller runs:
- FastAPI backend
- React panel
- PostgreSQL
- Redis

It owns customer identity, plans, inventory, orchestration state and audit history.

### StorServer Agent

Each game node runs a small agent. The agent:
- talks to the local Docker Engine through `/var/run/docker.sock`
- provisions game containers
- enforces resource limits
- allocates ports
- streams logs and status
- performs lifecycle operations

The control plane talks to agents using authenticated HTTPS. The initial development stack uses a shared bootstrap token; production will move to per-node rotated credentials and mTLS.

### Game templates

Templates live under `games/` and define:
- Steam App ID / installer type
- container runtime image
- game/query/Steam/web-admin ports
- persistent volumes
- environment and startup metadata

A catalog entry stays disabled until its runtime image and network behavior have passed integration tests.

## Multi-tenancy

All customer-owned resources carry an owner identifier. Authorization is enforced in the API before requests reach a node.

Production milestones include:
- plans and quotas
- per-customer server limits
- per-node capacity scheduling
- immutable audit records
- support/operator roles
- API keys scoped by tenant

## Public game websites

The public-sites subsystem will generate a site for each game server, for example:

`kf-storm.hoststorm.cloud`

The recommended DNS model is a wildcard record for `*.hoststorm.cloud` pointing at the public-site ingress. TLS can be issued with a wildcard certificate using a DNS-01 challenge.

The public site layer remains separate from the customer/admin panel and will expose only curated public data such as status, players, map, rules, Discord and branding.

## Networking

Game nodes publish only the ports assigned to a server. StorServer tracks allocations to prevent collisions.

For Oracle or other cloud providers, cloud firewall/security-list automation will be implemented as a provider module instead of ad-hoc iptables commands.

Provider abstraction target:

```text
NetworkProvider
  allocate_port()
  release_port()
  ensure_ingress_rule()
  remove_ingress_rule()
  resolve_public_address()
```

This allows Oracle, bare-metal, Unraid labs and future providers to use the same control plane.

## Production security targets

- mTLS or mutually authenticated agent tunnel
- node credentials encrypted at rest
- secret rotation
- 2FA for admins
- rate limiting
- session revocation
- CSRF-safe browser auth strategy
- no privileged game containers by default
- AppArmor/seccomp profiles where supported
- read-only root filesystems where practical
- backup encryption
- vulnerability scanning in CI
