# CStation Strategic Roadmap 🗺️

This document outlines the strategic roadmap, architectural evolution, and milestone releases for **CStation**.

---

## 🎯 Strategic Vision

CStation is engineered as a **local-first DevOps operating system** designed to eliminate cloud vendor lock-in, streamline declarative infrastructure management, and provide high-speed (<100ms) fleet orchestration.

```
       Phase 1-3              Phase 4-5               Phase 6-7              Phase 8+
 ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
 │ VPS Lifecycle    │──▶│ Declarative      │──▶│ Odoo Enterprise  │──▶│ Autonomous Fleet │
 │ & Fact Caching   │   │ Containers & DNS │   │ Pipelines & Sync │   │ & Auto-Healing   │
 └──────────────────┘   └──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## 🚦 Phase Overview & Status

| Phase | Milestone | Focus Area | Status | Target / Completed |
|---|---|---|---|---|
| **Phase 1** | **Foundation & Architecture** | Python 3.13, Typer, Pydantic V2, Config Resolution | ✅ Complete | 2026-Q1 |
| **Phase 2** | **High-Speed SSH & Facts** | `SSHManager`, `run_batch()`, `.facts.json` (<100ms) | ✅ Complete | 2026-Q2 |
| **Phase 3** | **VPS 13-Phase Pipeline** | Idempotent OS setup, UFW, BBR tuning, Docker engine | ✅ Complete | 2026-Q2 |
| **Phase 4** | **Declarative Docker Engine** | Fragments, `ImageService`, `OdooService`, `TraefikService` | ✅ Complete | 2026-Q2 |
| **Phase 5** | **Cloudflare DNS & Netcup Auth** | Declarative DNS drift detection, OAuth2 SCP auth | ✅ Complete | 2026-Q3 |
| **Phase 6** | **Enterprise Odoo Pipelines** | Fast rsync delta sync, auto-backup fetching, restores | ✅ Complete | 2026-Q3 |
| **Phase 7** | **Multi-Arch Image Builder** | Podman/Docker manifest generation, multi-arch push | 🔄 Active | 2026-Q3 |
| **Phase 8** | **Autonomous Health & Self-Healing** | Real-time container health probes & automated restarts | 📅 Planned | 2026-Q4 |
| **Phase 9** | **Multi-Cloud Provisioning API** | Hetzner Cloud, Vultr, and Netcup server spin-up | 📅 Planned | 2027-Q1 |
| **Phase 10** | **AI Agent Memory & Telemetry** | Hindsight memory bank integration for fleet topology | 📅 Planned | 2027-Q2 |

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
- [ ] **Automated OS Upgrade Helper**:
  - Guided LTS upgrades (e.g. Ubuntu 24.04 -> 26.04) with preflight dependency checks.

---

### Track B: Declarative Container Orchestration

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
- [ ] **Auto-Healing & Watchdog**:
  - Automated restart of unhealthy or restart-looping containers with alert webhooks.

---

### Track C: Odoo Enterprise Workflows

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
- [ ] **Multi-Version Migration Tooling**:
  - Built-in Odoo database upgrade scripts across versions (13.0 -> 15.0 -> 18.0).

---

### Track D: DNS & Cloud Integration

- [x] **Cloudflare DNS Management**:
  - Declarative DNS zone management in `~/.config/cstation/dns/`.
  - Automated drift detection between declared YAML and Cloudflare API.
- [x] **Provider Authentication**:
  - OAuth2 device-flow authentication for Netcup SCP (`cstation auth netcup login`).
- [ ] **Dynamic Multi-Cloud Provisioning**:
  - API provisioning adapters for Hetzner Cloud, Vultr, and Netcup to spin up new servers from scratch.

---

## 📈 Release Milestones

### v1.0.0 (Current Release)
- Full 13-phase VPS lifecycle pipeline.
- Declarative Docker engine with `ImageService`, `OdooService`, `TraefikService`.
- Multi-arch Docker/Podman image builder.
- Odoo backup, restore, and high-speed rsync sync.
- Fast selective GitHub cloning (`--filter=blob:none`).
- 244 automated unit and integration tests passing.

### v1.1.0 (Upcoming)
- Autonomous container health monitoring and webhook notifications.
- Interactive TUI (Text User Interface) for live multi-server fleet telemetry.
- Automated database migration pipelines.
