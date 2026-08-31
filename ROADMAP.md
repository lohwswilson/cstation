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
| **Phase 5** | **Cloudflare DNS Management** | Declarative DNS drift detection, zone sync | ✅ Complete | 2026-Q3 |
| **Phase 6** | **Enterprise Odoo Pipelines** | Fast rsync delta sync, auto-backup extraction, restores | ✅ Complete | 2026-Q3 |
| **Phase 7** | **CI/CD & Reliability Hardening** | GitHub Actions CI/CD workflow, PostgreSQL collation healing | ✅ Complete | 2026-Q3 |
| **Phase 8** | **Developer Ergonomics & UX** | `vps ssh` shell, interactive backup picker, `odoo update` | ✅ Complete | 2026-Q3 |
| **Phase 9** | **Parallel Fleet Telemetry** | Multi-threaded fleet refresh (`ThreadPoolExecutor`), backup prune | ✅ Complete | 2026-Q3 |
| **Phase 10** | **Autonomous Health & Healing** | Real-time container health probes & webhook alerts | 📅 Planned | 2026-Q4 |
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
- [x] **Interactive SSH Shell Shortcut (`cstation vps ssh <host>`)**:
  - Direct TTY shell connection using parsed host, port, user, and SSH key from `vps.yaml`.
- [x] **Parallel Multi-Node Fleet Refresh (`cstation vps list --refresh`)**:
  - Multi-threaded fact collection via `concurrent.futures.ThreadPoolExecutor` for live fleet refresh.
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
- [x] **PostgreSQL Collation Self-Healing**:
  - Automated check and execution of `ALTER DATABASE template1 REFRESH COLLATION VERSION;` during PostgreSQL 18+ container deployment and database restores.
- [x] **Pre-Flight Secret & DNS Verification in `cstation check`**:
  - Cross-check declared `secrets:` in all container fragments against `~/.config/cstation/config.yaml` and schema-validate DNS zone definitions.
- [ ] **Live Container Drift Detection**:
  - Compare running container image digest/tags against declared fragments in `docker plan`.
- [ ] **Autonomous Health & Watchdog**:
  - Automated restart of unhealthy or restart-looping containers with alert webhooks.

---

### Track C: Odoo Enterprise Workflows & Database Operations

- [x] **Optimized Code Synchronization**:
  - Selective rsync syncing `PW.<version>` and `PW_ADDONS.<version>` to target VPS.
  - Dry-run validation to preview changed files before syncing.
- [x] **Direct Odoo Module Update Command (`cstation odoo update`)**:
  - Run database module upgrades (`odoo -u <module> -d <db> --stop-after-init`) directly over SSH.
- [x] **Automated Backup Extraction & Server-Side Pruning**:
  - Intelligent search across timestamped dump archives in `/var/lib/odoo/backups/`.
  - Manifest verification (`manifest.json`) to guarantee database identity.
  - `--keep <N>` retention policy to auto-purge older backup files from container.
- [x] **Complete Zero-Downtime Restores & Interactive Picker**:
  - Interactive backup selection menu when restoring without explicit file argument.
  - Automated database creation, collation verification, and `dump.sql` restore.
  - Complete filestore directory transfer with 256 checklist subdirectories.
  - Strict exit code error trapping across all restore commands.
- [ ] **Multi-Version Migration Tooling**:
  - Built-in Odoo database upgrade scripts across versions (13.0 -> 15.0 -> 18.0).

---

### Track D: DNS & Multi-Cloud Provider Automation

- [x] **Cloudflare DNS Management**:
  - Declarative DNS zone management in `~/.config/cstation/dns/`.
  - Automated drift detection between declared YAML and Cloudflare API.
- [ ] **Dynamic Multi-Cloud Provisioning**:
  - API provisioning adapters for Hetzner Cloud, Vultr, and Netcup to spin up new servers from scratch.

---

### Track E: CI/CD, Tooling & Developer Quality

- [x] **Automated GitHub Actions CI/CD Pipeline**:
  - Run all unit and integration tests automatically on every push and pull request via `.github/workflows/ci.yml`.
- [x] **Ruff Linter & Code Formatter**:
  - Configured `[tool.ruff]` in `pyproject.toml` with 100% compliant formatting.
- [x] **Release v1.0.0 Packaging**:
  - Package bumped to `1.0.0` (`Production/Stable`).
- [ ] **Declarative Config Version Control (`cstation config sync`)**:
  - Automated Git synchronization for `~/.config/cstation/` with `.gitignore` excluding `config.yaml`.

---

## 📈 Release Milestones

### v1.0.0 (Production Release — Completed)
- Full 13-phase VPS lifecycle pipeline & `vps ssh` remote shell.
- Multi-threaded parallel fleet refresh (`cstation vps list --refresh`).
- Declarative Docker engine with `ImageService`, `OdooService`, `TraefikService`.
- Multi-arch Docker/Podman image builder.
- Odoo backup (with `--keep` pruning), interactive restore picker, and `odoo update` module upgrade command.
- PostgreSQL collation self-healing and strict restore error traps.
- Pre-flight secret validation and DNS zone checking in `cstation check`.
- Automated GitHub Actions CI workflow (Ubuntu + macOS matrix on Python 3.13).
- Ruff linting and formatting standards.
- 250 automated unit and integration tests passing in 1.12s.

### v1.1.0 (Upcoming Milestone)
- Declarative config Git sync (`cstation config sync`).
- Live container image digest drift detection.
- Lazy subcommand loading for instant (<15ms) CLI startup.
- Autonomous container health monitoring and webhook notifications.
- Multi-cloud server provisioning APIs (Hetzner, Vultr, Netcup).
