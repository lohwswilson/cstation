# CStation 🚀

[![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Package Manager](https://img.shields.io/badge/uv-fast-green.svg)](https://docs.astral.sh/uv/)
[![Build Backend](https://img.shields.io/badge/build-hatchling-orange.svg)](https://hatch.pypa.io/)
[![Test Suite](https://img.shields.io/badge/tests-250%20passed-success.svg)](https://pytest.org/)
[![Release](https://img.shields.io/badge/release-v1.0.0-blue.svg)](https://github.com/lohwswilson/cstation)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)]()

**CStation** is a modern, local-first DevOps CLI and Infrastructure-as-Code (IaC) orchestrator. It manages VPS lifecycle, declarative Docker container stacks, multi-architecture image builds, Cloudflare DNS zones, and end-to-end Odoo deployments with sub-100ms response times.

---

## 📑 Table of Contents

- [Key Highlights](#-key-highlights)
- [System Architecture](#-system-architecture)
- [Installation & Setup](#-installation--setup)
- [Command Hierarchy](#-command-hierarchy)
- [Quickstart Workflows](#-quickstart-workflows)
  - [1. Interactive TUI Dashboard & Command Palette](#1-interactive-tui-dashboard--command-palette)
  - [2. VPS Lifecycle & Remote Shell](#2-vps-lifecycle--remote-shell)
  - [3. Declarative Docker Containers](#3-declarative-docker-containers)
  - [4. Enterprise Odoo Deployments & Updates](#4-enterprise-odoo-deployments--updates)
  - [5. AI Memory Service (Hindsight)](#5-ai-memory-service-hindsight)
  - [6. Configuration Portability (Export & Import)](#6-configuration-portability-export--import)
  - [7. SQLite Runtime State & Operational Audit](#7-sqlite-runtime-state--operational-audit)
  - [8. Declarative DNS (Cloudflare)](#8-declarative-dns-cloudflare)
  - [9. Multi-Arch Docker Image Builds](#9-multi-arch-docker-image-builds)
  - [10. GitHub Repository Management](#10-github-repository-management)
- [Configuration Structure](#-configuration-structure)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Documentation Suite](#-documentation-suite)

---

## ✨ Key Highlights

- **⚡ Blazing Fast Telemetry (<100ms)**: Bundles multi-command SSH queries into single roundtrips using `run_batch()` (`==CS_SEP==` separator), parallel multi-node refresh via `ThreadPoolExecutor`, and caches facts in local `.facts.json`.
- **🛡️ 100% Declarative & Safe**: Powered by Pydantic V2 schemas. Every mutating command includes an interactive `plan` mode before `apply`.
- **💻 Local-First Single Source of Truth**: All infrastructure state lives in `~/.config/cstation/` as version-controllable YAML.
- **🐳 Declarative Docker Stacks**: Lightweight fragment files generate production `docker-compose.yml`, `.env`, Traefik reverse-proxy configs, and systemd mounts on-the-fly.
- **🔄 Enterprise Odoo Pipelines**: High-speed delta `rsync` code synchronizers, remote module updates (`odoo update`), automated backup extraction with manifest verification, server-side retention pruning (`--keep <N>`), interactive restore picker, and automated PostgreSQL collation self-healing.
- **🌐 Cloud-Agnostic with DNS Automation**: Manages Hetzner, Vultr, Netcup, and static bare-metal servers alongside automated Cloudflare DNS ACME challenges.

---

## 🏛️ System Architecture

```mermaid
graph TD
    CLI[cstation CLI / Typer App] --> Config[ConfigManager: ~/.config/cstation/]
    CLI --> SSH[SSHManager: Fabric / Paramiko / run_batch]
    
    Config --> Models[Pydantic V2 Models]
    Config --> Secrets[Secrets Engine: config.yaml]
    
    CLI --> VPS[VPS Engine: 13-Phase Pipeline]
    CLI --> Docker[Docker Engine: Declarative Fragments]
    CLI --> Odoo[Odoo Engine: Sync / Update / Backup / Restore]
    CLI --> DNS[DNS Engine: Cloudflare API]
    CLI --> Image[Image Builder: Docker / Podman]
    CLI --> GitHub[GitHub Manager: Selective Clone]
    
    VPS --> |SSH Batch| RemoteHost[Remote VPS Host]
    Docker --> |Compose & Traefik| RemoteHost
    Odoo --> |rsync & psql| RemoteHost
```

---

## 📦 Installation & Setup

### Prerequisites
- **Python 3.13+** (pinned via `.python-version`)
- [**`uv`**](https://docs.astral.sh/uv/) (recommended high-performance package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/lohwswilson/cstation.git
cd cstation

# Install in editable mode with development & test extras
uv pip install -e ".[test]"

# Verify installation
cstation --help
```

---

## 🛠️ Command Hierarchy

```
cstation
├── tui          # Interactive terminal dashboard & fuzzy command palette (Ctrl+P) (aliases: dashboard, ui)
├── config       # Configuration portability: export/import bundles & safety rollback
├── state        # SQLite operational audit logs & time-series resource telemetry
├── vps          # VPS lifecycle (init, plan, apply, status, list, ssh, rm)
├── docker       # Declarative container stacks (plan, apply, status, import, rm)
├── odoo         # Odoo workflows (sync, update, backup, restore)
├── hindsight    # Hindsight AI memory service (status, backup)
├── image        # Docker image build & registry push (list, build)
├── dns          # DNS zone & record management (zones, plan, apply)
├── github       # GitHub repo & SSH management (repo list, sync, clone, ssh)
├── check        # Offline pre-flight linter & schema validator (alias: lint)
├── completion   # Shell auto-completion helpers (install, show)
└── server       # Server playbooks & Ansible subcommands
```

---

## 🚀 Quickstart Workflows

### 1. Interactive TUI Dashboard & Command Palette

```bash
# Launch interactive terminal UI
cstation tui  # (or: cstation dashboard)

# Inside the TUI:
# - Press Ctrl+P: Open fuzzy command palette to search & run any command
# - Up/Down / j/k: Select VPS node to inspect container stacks
# - [p]: Dry-run docker plan on selected VPS
# - [r]: Refresh server fleet telemetry
# - [l]: Run pre-flight linting
# - [q]: Quit
```

### 2. VPS Fleet Lifecycle & Remote Shell

```bash
# Add a new remote server (interactive wizard or non-interactive flags)
cstation vps add
cstation vps add prod-web-01 --host 107.155.65.47 --user root --stage prod
cstation vps add staging-app --host 198.51.100.5 --skip-facts

# List all VPS nodes with parallel live telemetry refresh
cstation vps list --refresh

# View live hardware metrics for a specific node
cstation vps status sg01.synercatalyst.com

# Open direct interactive SSH shell
cstation vps ssh sg01.synercatalyst.com

# Dry-run 13-phase OS setup pipeline
cstation vps plan sg01.synercatalyst.com

# Apply complete hardened OS baseline (firewall, swap, BBR tuning, fail2ban, docker)
cstation vps apply sg01.synercatalyst.com --yes

# Remove a VPS from local configuration and purge its secrets
cstation vps remove prod-web-01 --yes
```

### 3. Declarative Docker Containers

```bash
# Import all running containers on a VPS into local YAML fragments
cstation docker import sg01.synercatalyst.com --all

# Preview container drift and compose changes
cstation docker plan sg01.synercatalyst.com

# Deploy / update container stacks over SSH
cstation docker apply sg01.synercatalyst.com --yes
```

### 4. Enterprise Odoo Deployments & Updates

```bash
# Sync local PW.18.0 and addons to VPS via optimized rsync
cstation odoo sync sg01 18.0

# Sync a specific module only (auto-discovers location across PW_ADDONS in <1s)
cstation odoo sync sg01 15.0 -m perfectwork_sg_be

# Upgrade an Odoo database module directly over SSH
cstation odoo update sg01 SG01_DEV5_SG01DB -d be5 -m perfectwork_sg_be

# Download auto-backup and retain only the 7 newest archives on the remote host
cstation odoo backup us01.synercatalyst.com US01_BESOLUTION_US01DB PW5-BESOLUTION --keep 7

# Restore backup zip (auto-prompts with local backup picker if zip omitted)
cstation odoo restore sg01.synercatalyst.com SG01_DEV5_SG01DB --dest-db be5 --yes
```

### 5. AI Memory Service (Hindsight)

```bash
# Inspect Hindsight container status, ports, and latest remote backup
cstation hindsight status sg07.ansis.com.sg

# Download remote database backup dump and retain only the 5 newest local copies
cstation hindsight backup sg07.ansis.com.sg --dest ~/.hermes/backups/hindsight --keep 5
```

### 6. Configuration Portability (Export & Import)

```bash
# Export full fleet configuration to a portable timestamped .tar.gz bundle
cstation config export

# Export sanitized template without secrets (.env, tokens)
cstation config export --no-secrets --out ~/Downloads/cstation-template.tar.gz

# Preview archive import without modifying disk
cstation config import ~/Downloads/cstation-fleet.tar.gz --dry-run

# Import and restore (creates automatic rollback safety backup prior to extracting)
cstation config import ~/Downloads/cstation-fleet.tar.gz
```

### 7. SQLite Runtime State & Operational Audit

```bash
# View operational audit log of user & agent commands
cstation state audit

# View historical hardware resource snapshots for a VPS
cstation state history sg05.ansis.com.sg

# Retrieve audit trail as machine-readable JSON for AI agents
cstation state audit --output json
```

### 8. Declarative DNS (Cloudflare)

```bash
# List all configured Cloudflare DNS zones
cstation dns zones

# Dry-run DNS drift against ~/.config/cstation/dns/
cstation dns plan synercatalyst.com

# Apply declared DNS records
cstation dns apply synercatalyst.com --yes
```

### 9. Multi-Arch Docker Image Builds

```bash
# List available image recipes in ~/.config/cstation/images/
cstation image list

# Build multi-arch image and push to configured registry
cstation image build synercatalyst-odoo.13.0
```

### 10. GitHub Repository Management

```bash
# View configured repository mappings
cstation github repo list

# Fast selective clone (blobless --filter=blob:none in parallel)
cstation github repo clone

# Sync fork with upstream repository
cstation github repo sync
```

---

## 📂 Configuration Structure

All live configurations reside under `~/.config/cstation/`:

```
~/.config/cstation/
├── config.yaml                     # Global credentials, secrets, & API tokens
├── vps/                            # Server configs & container stacks
│   ├── sg01.synercatalyst.com/
│   │   ├── vps.yaml                # VPS hardware, access & OS baseline
│   │   ├── .facts.json             # Cached hardware & status telemetry
│   │   ├── SG01_DB.yaml            # PostgreSQL database container fragment
│   │   ├── SG01_TRAEFIK.yaml       # Traefik reverse proxy fragment
│   │   ├── SG01_PORTAINER.yaml     # Portainer CE fragment
│   │   └── SG01_DEV8_SG01DB.yaml   # Odoo 18.0 container stack fragment
│   ├── sg07.ansis.com.sg/
│   └── us01.synercatalyst.com/
├── dns/                            # Declarative DNS zones (synercatalyst.com.yaml)
├── github/                         # Git repository sync definitions (odoo_repos.sync.yml)
└── images/                         # Multi-arch Docker image build recipes
```

---

## 🧪 Testing & Quality Assurance

CStation maintains an extensive automated test suite covering CLI invocation, SSH batch execution, model schemas, and error boundaries:

```bash
# Run all tests with pytest
uv run pytest -q

# Run specific test modules
uv run pytest tests/commands/test_docker_cli.py
uv run pytest tests/commands/test_vps_cli.py
uv run pytest tests/commands/test_odoo_cli.py
```

---

## 📚 Documentation Suite

- 📘 **[CStation User Guide (docs/user-guide.md)](docs/user-guide.md)**: End-to-end practical walkthrough and workflows.
- 📖 **[CLI Command Reference (docs/cli-reference.md)](docs/cli-reference.md)**: Complete manual for all 15 command groups.
- ⚙️ **[Configuration Guide (docs/configuration-guide.md)](docs/configuration-guide.md)**: Comprehensive YAML schema reference.
- 🏛️ **[System Architecture (ARCHITECTURE.md)](ARCHITECTURE.md)**: Deep dive into CStation internals, SSH batching, and service adapters.
- 🗺️ **[Strategic Roadmap (ROADMAP.md)](ROADMAP.md)**: Phased milestones, tracks, and future capabilities.
- 🤝 **[Developer & Contributing Guide (CONTRIBUTING.md)](CONTRIBUTING.md)**: Contribution standards, code style, and PR workflow.
- 🤖 **[AI Agent Guidance (AGENTS.md)](AGENTS.md)**: Canonical rules for AI coding agents.
