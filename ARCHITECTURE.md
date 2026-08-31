# CStation System Architecture 🏛️

This document describes the internal architecture, design principles, and subsystem implementations of **CStation**.

---

## 📐 Core Design Principles

1. **Local-First Infrastructure-as-Code (IaC)**:
   - The single source of truth for all VPS nodes, container fragments, DNS zones, and image builds is stored locally in `~/.config/cstation/`.
   - No remote state database or centralized daemon is required.
2. **Sub-100ms Response Latency**:
   - Status checks and fleet listing execute in under 100ms by utilizing local cached facts (`.facts.json`) and batch SSH roundtrips.
3. **Strict Declarative Idempotency**:
   - Every state transition supports a dry-run `plan` phase before `apply`.
   - Applying a configuration multiple times produces the exact same end state without side effects.
4. **Strong Typing & Error Boundaries**:
   - 100% typed using **Pydantic V2**.
   - Input validation errors are intercepted at boundaries with precise field locations and error messages.

---

## 🧩 System Architecture Overview

```
                      ┌─────────────────────────────────────────┐
                      │              cstation CLI               │
                      │  (Typer Multi-Command Application)      │
                      └────────────────────┬────────────────────┘
                                           │
                ┌──────────────────────────┼──────────────────────────┐
                ▼                          ▼                          ▼
      ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
      │  Config Manager  │       │   SSH Manager    │       │  Pydantic Models │
      │ ~/.config/cstation│       │   (run_batch)    │       │   (Pydantic V2)  │
      └─────────┬────────┘       └─────────┬────────┘       └─────────┬────────┘
                │                          │                          │
   ┌────────────┴──────────────────────────┴──────────────────────────┴────────────┐
   │                                                                               │
   ▼                                       ▼                                       ▼
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│       VPS Engine        │     │      Docker Engine      │     │       Odoo Engine       │
│  (13-Phase Pipeline)    │     │  (Image / Odoo / Proxy) │     │  (Sync / Backup / Rest) │
└───────────┬─────────────┘     └───────────┬─────────────┘     └───────────┬─────────────┘
            │                               │                               │
            └───────────────────────────────┼───────────────────────────────┘
                                            ▼
                              ┌───────────────────────────┐
                              │     Remote VPS Hosts      │
                              │  (SSH / Docker / Compose) │
                              └───────────────────────────┘
```

---

## ⚙️ Subsystem Deep Dives

### 1. Configuration Engine & 3-Tier Precedence

CStation loads and merges YAML configuration files using a strictly defined 3-tier precedence hierarchy:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Directory:   ~/.config/cstation/   (Highest Priority)│
├─────────────────────────────────────────────────────────────┤
│ 2. System Directory: /etc/cstation/        (Medium Priority) │
├─────────────────────────────────────────────────────────────┤
│ 3. Default Bundle:   ./etc/                (Lowest Priority)  │
└─────────────────────────────────────────────────────────────┘
```

- **Load Boundary Safety**: `initialize_configuration()` loads configuration once per process lifecycle.
- **Secrets Isolation**: Sensitive credentials (database passwords, API keys) live in `config.yaml` and are dynamically injected during container deployment rather than hardcoded in public fragments.

---

### 2. SSH Execution Engine & `run_batch()` Protocol

To avoid the multi-second latency penalty of standard sequential SSH roundtrips, CStation implements the `run_batch()` protocol in [`src/cstation/ssh.py`](src/cstation/ssh.py):

```python
# Batch multiple shell commands into a single round-trip:
separator = "==CS_SEP=="
batched_script = f"\n echo '{separator}'\n ".join(commands)
raw_output = ssh.run(batched_script, hide=True)
results = raw_output.split(separator)
```

This protocol allows CStation to collect system facts (CPU, memory, load average, disk usage, container states) in a **single SSH roundtrip**, reducing inspection time from >5 seconds down to ~300ms.

---

### 3. Fact Caching System (`.facts.json`)

To achieve instant (<100ms) command response times for `cstation vps list` and `cstation vps status`:
- Hardware facts, OS information, and container summaries are persisted to `.facts.json` within each VPS config directory (`~/.config/cstation/vps/<host>/.facts.json`).
- Each cached fact contains a `_cached_at` ISO-8601 timestamp.
- Running `cstation vps status <host> --refresh` triggers a live SSH scan and updates the cache.

---

### 4. VPS 13-Phase Infrastructure Pipeline

When executing `cstation vps apply <host>`, CStation executes 13 idempotent setup phases in exact order:

```
 1. packages           Install baseline packages (ufw, fail2ban, docker.io, docker-compose-v2)
 2. shell              Configure bash environment, PATH, and prompt
 3. terminal           TTY and locale settings (en_US.UTF-8)
 4. sshd               Harden SSH daemon (PasswordAuthentication no, port configuration)
 5. firewall           Configure UFW firewall with default deny and explicit port rules
 6. swap               Create and activate swapfile with swappiness tuning
 7. tuning             Apply sysctl kernel optimizations (TCP BBR, socket buffers)
 8. fail2ban           Configure Fail2ban jails with nftables backend
 9. hostname           Apply system hostname
10. docker_daemon      Write /etc/docker/daemon.json (log rotation, live-restore)
11. docker_networks    Create declared bridge networks (e.g. PW_NET)
12. docker_directories Create declared persistent host bind directories
13. fact_collection    Collect live hardware telemetry and update .facts.json
```

Every phase accepts a `dry_run: bool` parameter. When `dry_run=True` (invoked via `cstation vps plan`), the phase inspects the remote state and reports what changes *would* be made without executing mutating commands.

---

### 5. Declarative Docker Service Engine

CStation employs a service class hierarchy for managing Docker containers:

```
                      ┌──────────────────────┐
                      │     ImageService     │
                      │  (Base Docker Stack) │
                      └──────────┬───────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
      ┌──────────────────────┐        ┌──────────────────────┐
      │     OdooService      │        │    TraefikService    │
      │ (odoo.conf, workers) │        │ (ACME SSL, Routers)  │
      └──────────────────────┘        └──────────────────────┘
```

- **`ImageService`**: Handles directory creation, `.env` generation from secrets, `docker-compose.yml` generation, and `docker compose up -d`.
- **`OdooService`**: Automatically renders `/var/lib/odoo/odoo.conf` with configured addons search paths, database filters (`dbfilter = ^%d$`), performance worker tuning, and creates the required PostgreSQL user and database.
- **`TraefikService`**: Generates dynamic file provider configuration files under `/var/lib/traefik/conf/<service>.yml`, handles wildcard domain matching (`HostRegexp`), and configures websocket routing to port `8072`.

---

### 6. Reverse Proxy & Wildcard Ingress (Traefik)

CStation integrates Traefik as the default edge router:

```mermaid
graph LR
    Client[Web Browser] --> |HTTPS :443| Traefik[Traefik Reverse Proxy]
    
    Traefik --> |HTTP :8069 (Web Traffic)| OdooWeb[Odoo HTTP Worker]
    Traefik --> |HTTP :8072 (/websocket & /longpolling)| OdooWS[Odoo Longpolling Worker]
    
    Traefik --> |Cloudflare DNS ACME| LetEncrypt[Let's Encrypt Wildcard SSL]
    OdooWeb --> |PostgreSQL 5432| DB[(PostgreSQL 18 + pgvector)]
```

- **DNS Challenge ACME**: Uses Cloudflare DNS API (`le_dns_resolver`) to generate wildcard certificates (`*.domain.com`) without exposing port 80 during challenges.
- **Automatic Websocket Splitting**: Requests matching `/websocket` or `/longpolling` are routed directly to the evented longpolling port (`8072`), while standard HTTP requests go to the multi-worker port (`8069`).

---

### 7. Security & Secrets Isolation Model

- **Zero Plaintext Secrets in Repos**: Container fragments declare which secret keys they require (e.g. `secrets: [PASSWORD, POSTGRES_PASSWORD]`).
- **Centralized Secrets Store**: The real credentials are kept in the user's `~/.config/cstation/config.yaml` (which is excluded from public Git repositories).
- **At-Rest & In-Flight Security**: All remote execution uses SSH Key authentication (`PasswordAuthentication no`). Firewalls deny all incoming traffic except explicit ports.
