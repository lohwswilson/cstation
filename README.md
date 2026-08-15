# CStation 🚀

**CStation** is a modern, local-first DevOps CLI for managing VPS infrastructure, declarative Docker container stacks, multi-arch Docker image builds, Cloudflare DNS records, and Odoo deployments.

Built with Python 3.13, Typer, Pydantic V2, and `uv`.

---

## ✨ Key Highlights

- **⚡ Blazing Fast (<100ms)**: Employs bundled SSH batch execution (`run_batch`) and local fact caching (`.facts.json`) for instant status dashboards and zero-latency fleet listings.
- **🛡️ Declarative & Safe**: 100% typed with Pydantic V2. Every command supports dry-run `plan` modes before executing `apply`.
- **💻 Local-First Architecture**: Your `~/.config/cstation/` directory is the single source of truth—commit it to Git to manage infrastructure as code.
- **📦 Declarative Docker Orchestration**: Declare container stacks as lightweight YAML fragments alongside VPS definitions. Compose files are generated and applied on-the-fly over SSH.
- **🔄 Complete Odoo Workflows**: High-speed delta `rsync` code synchronization, automated container backup fetching, and full database + filestore restores.
- **🌐 Vendor-Neutral DNS & Auth**: Declarative DNS record synchronization via Cloudflare, and automated OAuth2 device-flow authentication for Netcup SCP.

---

## 📦 Installation & Setup

### Prerequisites
- Python **3.13+**
- [`uv`](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/lohwswilson/cstation.git
cd cstation

# Install in editable mode
uv pip install -e .

# (Optional) Install test dependencies
uv pip install -e ".[test]"

# Verify installation
cstation --version
cstation --help
```

---

## 🛠️ Command Overview

```
cstation
├── vps          # VPS lifecycle (init, plan, apply, status, list, rm)
├── docker       # Declarative container stacks (plan, apply, status, import, restart)
├── odoo         # Odoo workflows (sync, backup, restore)
├── image        # Docker image build & registry push (build, list, show)
├── dns          # DNS zone & record management (zones, plan, apply)
├── auth         # Provider authentication (netcup login, logout, status)
├── github       # GitHub repo & SSH management (repo list, sync, clone, ssh)
├── server       # Ansible playbook runner & server tools
└── version      # Print CStation version
```

---

## 🚀 Quickstart Guide

### 1. VPS Management

```bash
# 1. Initialize a new VPS config via live SSH scan
cstation vps init sg01.synercatalyst.com --port 22 --user root

# 2. Preview 12-phase OS setup (packages, firewall, sshd, swap, tuning, docker)
cstation vps plan sg01.synercatalyst.com

# 3. Apply baseline configuration
cstation vps apply sg01.synercatalyst.com --yes

# 4. View real-time VPS health dashboard (CPU, RAM, Disk, Docker)
cstation vps status sg01.synercatalyst.com

# 5. List all managed VPS instances
cstation vps list
```

### 2. Declarative Docker Containers

```bash
# 1. Scrape existing containers from a VPS into local YAML fragments
cstation docker import sg01.synercatalyst.com --all

# 2. Check running vs declared container state
cstation docker status sg01.synercatalyst.com

# 3. Dry-run container changes
cstation docker plan sg01.synercatalyst.com

# 4. Deploy or update containers via SSH
cstation docker apply sg01.synercatalyst.com --yes
```

### 3. Odoo Code Sync & Database Backups

```bash
# Sync local PW.18.0 and addons to VPS via optimized rsync
cstation odoo sync sg06 18.0

# Preview sync without touching remote files
cstation odoo sync sg06 18.0 --dry-run

# Download the latest auto-backup from a running container
cstation odoo backup sg01 SG01_PROD my_database

# Restore a full backup zip (database dump + filestore)
cstation odoo restore sg01 SG01_PROD backup.zip --yes
```

### 4. Declarative DNS (Cloudflare)

```bash
# List all Cloudflare DNS zones
cstation dns zones

# Dry-run DNS drift against ~/.config/cstation/dns/
cstation dns plan synercatalyst.com

# Apply DNS records
cstation dns apply synercatalyst.com --yes
```

### 5. Multi-Arch Docker Image Builds

```bash
# List available image recipes in ~/.config/cstation/images/
cstation image list

# Build multi-arch image and push to registry
cstation image build synercatalyst-odoo.13.0
```

### 6. GitHub Repository Management & Fast Selective Clone

```bash
# View configured repository mapping
cstation github repo list

# Fast selective clone (blobless --filter=blob:none & parallel worker threads)
cstation github repo clone

# Clone a single specific repository (e.g. OCA rest-framework)
cstation github repo clone rest-framework

# Fetch upstream (odoo/odoo), merge, pull origin, and push to GitHub fork
cstation github repo sync
```

---

## 📂 Configuration Structure

Live configurations are stored under `~/.config/cstation/`:

```
~/.config/cstation/
├── config.yaml                     # Global credentials, secrets, & API tokens
├── vps/                            # Server configs & container stacks
│   ├── sg01.synercatalyst.com/
│   │   ├── vps.yaml                # Infrastructure definition
│   │   ├── traefik.yaml            # Traefik reverse proxy fragment
│   │   ├── db.yaml                 # PostgreSQL container fragment
│   │   └── sg01_prod.yaml          # Odoo application fragment
│   └── us02.synercatalyst.com/
├── dns/                            # Declarative DNS zones (synercatalyst.com.yaml)
├── github/                         # Git repository sync definitions (odoo_repos.sync.yml)
└── images/                         # Multi-arch Docker image recipes
```

See the [Configuration Guide](docs/configuration-guide.md) for full schema specifications.

---

## 🧪 Testing & Development

```bash
# Run entire test suite (192 unit & integration tests)
uv run pytest -v

# Run single test module
uv run pytest tests/commands/test_vps_cli.py
```

---

## 📚 Detailed Documentation

- 📖 [CLI Command Reference](docs/cli-reference.md)
- ⚙️ [Configuration & Schema Guide](docs/configuration-guide.md)
- 🤖 [Coding Agent Guidance (AGENTS.md)](AGENTS.md)
