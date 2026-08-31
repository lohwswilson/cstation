# CStation Strategic Roadmap 🗺️

This document outlines the strategic roadmap, architectural evolution, and milestone releases for **CStation**.

---

## 🎯 Strategic Vision

CStation is engineered as a **local-first DevOps operating system** designed to eliminate cloud vendor lock-in, streamline declarative infrastructure management, and provide high-speed (<100ms) fleet orchestration.

```
       Phase 1-3              Phase 4-6               Phase 7-9             Phase 10-12
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
 │ VPS Lifecycle    │──▶│ Declarative      │──▶│ Enterprise Odoo, │──▶│ Autonomous Fleet,│
 │ & Fact Caching   │   │ Containers & DNS │   │ Reliability & UX │   │ Multi-Cloud & AI │
 └──────────────────┘   └──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## 🚦 Phase Overview & Status

| Phase | Milestone | Focus Area | Status | Target / Completed |
|---|---|---|---|---|
| **Phase 1** | **Foundation & Architecture** | Python 3.13, Typer, Pydantic V2, Config Precedence | ✅ Complete | 2026-Q1 |
| **Phase 2** | **High-Speed SSH & Facts** | `SSHManager`, `run_batch()`, `.facts.json` (<100ms) | ✅ Complete | 2026-Q2 |
| **Phase 3** | **VPS 13-Phase Pipeline** | Idempotent OS setup, UFW, BBR tuning, Docker engine | ✅ Complete | 2026-Q2 |
| **Phase 4** | **Declarative Docker Engine** | Fragments, `ImageService`, `OdooService`, `TraefikService` | ✅ Complete | 2026-Q2 |
| **Phase 5** | **Cloudflare DNS & Netcup Auth** | Declarative DNS drift detection, OAuth2 SCP auth | ✅ Complete | 2026-Q3 |
| **Phase 6** | **Enterprise Odoo Pipelines** | Fast rsync delta sync, auto-backup extraction, restores | ✅ Complete | 2026-Q3 |
| **Phase 7** | **Reliability & DB Hardening** | PostgreSQL collation self-healing, strict restore error traps | 🔄 Next | 2026-Q3 |
| **Phase 8** | **Developer Ergonomics & UX** | `vps ssh` shell, interactive backup picker, lazy loading | 🔄 Next | 2026-Q4 |
| **Phase 9** | **Parallel Fleet Telemetry** | Multi-threaded fleet refresh (`ThreadPoolExecutor`), prune flags | 📅 Planned | 2026-Q4 |
| **Phase 10** | **Autonomous Health & Healing** | Real-time container health probes & webhook alerts | 📅 Planned | 2027-Q1 |
| **Phase 11** | **Multi-Cloud Provisioning API** | Hetzner Cloud, Vultr, and Netcup server spin-up | 📅 Planned | 2027-Q1 |
| **Phase 12** | **AI Agent Memory & Topology** | Hindsight memory bank integration for fleet topology | 📅 Planned | 2027-Q2 |

---

## 🔍 Detailed Track Roadmaps

### Track A: VPS Infrastructure & OS Hardening

- [x] **13-Phase Setup Pipeline**:
  - `packages`: Baseline APT/DNF packages (`ufw`, `fail2ban`, `docker.io`, `docker-compose-v2`, `containerd`, `rsync`, `git`, `curl`).
  - `sshd`: Port configuration, `PasswordAuthentication no`, SSH key enforcement.
  - `firewall`: UFW automated configuration with default deny and explicit port rules.
  - `swap`: Configurable swap allocation with fallback resizing.
  - `tuning`: High-performance TCP BBR congestion control, `vm.swappiness=10`, socket buffers.
  - `fail2ban`: Jails with automated unban intervals and nftables integration.
  - `docker_daemon`: `daemon.json` setup (`log-driver: json-file`, `max-size: 10m`, `live-restore: true`).
  - `docker_networks`: Pre-creation of global bridge networks (`PW_NET`, `ANSIS_NET`).
  - `docker_directories`: Pre-creation of standard persistent mount paths.
- [x] **Sub-100ms Fact Caching**:
  - Single SSH round-trip execution using `==CS_SEP==` separator.
  - Local caching in `.facts.json` with timestamp invalidation.
- [ ] **Interactive SSH Shell Shortcut (`cstation vps ssh <host>`)**:
  - Direct TTY shell connection using parsed host, port, user, and SSH key from `vps.yaml`.
- [ ] **Parallel Multi-Node Fleet Refresh**:
  - Multi-threaded fact collection via `concurrent.futures.ThreadPoolExecutor(max_workers=8)` for live fleet refresh.
- [ ] **Lazy Subcommand Loading**:
  - Dynamic imports for subcommands to reduce CLI base startup latency from ~45ms to `<15ms`.
- [ ] **Automated OS Upgrade Helper**:
  - Guided LTS upgrades (e.g. Ubuntu 24.04 -> 26.04) with preflight dependency checks.

---

### Track B: Declarative Container Orchestration & Database Hardening

- [x] **Declarative YAML Fragments**:
  - Service-specific inheritance (`ImageService`, `OdooService`, `TraefikService`).
  - Automatic `docker-compose.yml` and `.env` generation.
  - In-place container import (`cstation docker import <vps> --all`).
- [x] **Traefik Reverse Proxy Integration**:
  - Dynamic file provider generation in `/var/lib/traefik/conf/`.
  - Automated Cloudflare DNS challenge ACME certificates (`le_dns_resolver`).
  - Wildcard domain routers with regex host filtering (`HostRegexp`).
  - Dedicated longpolling / websocket routes (`/websocket`, `/longpolling` -> port `8072`).
- [x] **PostgreSQL & Database Stacks**:
  - Support for `postgres:16`, `postgres:18`, and `pgvector/pgvector:pg18`.
  - Automatic database role creation with `CREATEDB` / superuser permissions.
- [ ] **PostgreSQL Collation Self-Healing**:
  - Automated check and execution of `ALTER DATABASE template1 REFRESH COLLATION VERSION;` during PostgreSQL 18+ container deployment to prevent collation version mismatch errors.
- [ ] **Live Container Drift Detection**:
  - Compare running container image digest/tags against declared fragments in `docker plan`.
- [ ] **Autonomous Health & Watchdog**:
  - Automated restart of unhealthy or restart-looping containers with alert webhooks.

---

### Track C: Odoo Enterprise Workflows & Database Operations

- [x] **Optimized Code Synchronization**:
  - Selective rsync syncing `PW.<version>` and `PW_ADDONS.<version>` to target VPS.
  - Dry-run validation to preview changed files before syncing.
- [x] **Automated Backup Extraction**:
  - Intelligent search across timestamped dump archives in `/var/lib/odoo/backups/`.
  - Manifest verification (`manifest.json`) to guarantee database identity.
- [x] **Complete Zero-Downtime Restores**:
  - Automated database creation, collation verification, and `dump.sql` restore.
  - Complete filestore directory transfer with 256 checklist subdirectories.
  - Automatic ownership and permission assignment (`chown 101:101`, `chmod 755`).
- [ ] **Strict Exit Code Error Traps in `odoo_restore`**:
  - Explicit assertion on `psql` command execution codes to prevent silent restore errors.
- [ ] **Interactive Backup Picker**:
  - Interactive selection menu when invoking `cstation odoo restore <vps> <container>` without a backup path argument.
- [ ] **Automated Backup Pruning (`--keep <N>`)**:
  - Retention policy parameter for `odoo backup` to prune archives older than N days / keep top N archives in `/var/lib/odoo/backups/`.
- [ ] **Multi-Version Migration Tooling**:
  - Built-in Odoo database upgrade scripts across versions (13.0 -> 15.0 -> 18.0).

---

### Track D: DNS & Multi-Cloud Provider Automation

- [x] **Cloudflare DNS Management**:
  - Declarative DNS zone management in `~/.config/cstation/dns/`.
  - Automated drift detection between declared YAML and Cloudflare API.
- [x] **Provider Authentication**:
  - OAuth2 device-flow authentication for Netcup SCP (`cstation auth netcup login`).
- [ ] **Dynamic Multi-Cloud Provisioning**:
  - API provisioning adapters for Hetzner Cloud, Vultr, and Netcup to spin up new servers from scratch.

---

### Track E: Tooling, Packaging & Developer Quality

- [ ] **Ruff Linter & Code Formatter**:
  - Configure `[tool.ruff]` in `pyproject.toml` for automated linting and formatting.
- [ ] **Release v1.0.0 Packaging**:
  - Bump package version to `1.0.0` in `pyproject.toml`.

---

## 📈 Release Milestones

### v1.0.0 (Current Release)
- Full 13-phase VPS lifecycle pipeline.
- Declarative Docker engine with `ImageService`, `OdooService`, `TraefikService`.
- Multi-arch Docker/Podman image builder.
- Odoo backup, restore, and high-speed rsync sync.
- Fast selective GitHub cloning (`--filter=blob:none`).
- 244 automated unit and integration tests passing.

### v1.1.0 (Upcoming Milestone)
- PostgreSQL collation self-healing in `OdooService`.
- Strict exit code verification in database restoration.
- `cstation vps ssh <host>` shortcut command.
- Interactive backup file selector.
- Ruff formatting & linting configuration.

### v1.2.0 (Fleet Scaling & Performance)
- Multi-threaded parallel fleet refresh (`--parallel`).
- Lazy subcommand loading for instant (<15ms) CLI startup.
- Automated backup pruning (`--keep <N>`).
- Autonomous container health monitoring and webhook notifications.
