# CStation - Infrastructure Management CLI

A DevOps CLI tool for managing VPS infrastructure, Docker container services, and deployments. Built with Python 3.13, Typer, and uv.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
git clone <repository-url>
cd cstation

# Install in editable mode
uv pip install -e .

# Install with test dependencies
uv pip install -e ".[test]"

# Verify
uv run cstation --help
```

## Quick Start

```bash
# List managed VPS instances
uv run cstation vps list

# Initialize a new VPS config using just SSH access
uv run cstation vps init your-server.com --port 8288

# Show live health dashboard for a server
uv run cstation vps status your-server.com

# Import existing containers from a VPS
uv run cstation docker import your-server.com
```

## Key Features

- **🚀 High-Performance SSH:** Uses bundled command execution (SSH Batching) and local fact caching to provide near-instantaneous status reports (<100ms).
- **🛡️ Universal Schema Safety:** *Every* configuration (VPS, Container, DNS, GitHub) is validated using Pydantic, catching errors before they touch your servers.
- **⚡ Native Orchestration:** Performs remote setup (OS hardening, Docker, GitHub SSH) directly via high-speed SSH. No Ansible dependency required for daily operations.
- **📦 Declarative Docker:** Manage containers as code. Import existing containers, plan changes with dry-runs, and apply updates via SSH-based Compose orchestration.
- **💻 Local-First:** Your `config/` directory is the single source of truth. Version control your infrastructure with Git.

## Installation

```bash
git clone <repository-url>
cd cstation

# Install using uv
uv pip install -e .

# Verify
uv run cstation --help
```

## Usage

### VPS Management

CStation uses a **"Local-First"** architecture. It performs parallel SSH checks but prioritizes local caching for speed.

```bash
# List all managed VPS instances (instantly shows cached health metrics)
cstation vps list

# Show live health dashboard (Load Avg, RAM, Disk, Docker status)
cstation vps status sg01.synercatalyst.com

# Force a live refresh (bypasses local cache)
cstation vps status sg01.synercatalyst.com --refresh

# Initialize a new VPS config via SSH scan
cstation vps init sg01.synercatalyst.com --port 22 --user root
```

### Docker Service Management

Manage your containers declaratively using YAML fragments.

```bash
# 1. Scrape existing containers from a VPS into local YAML files
cstation docker import sg01.synercatalyst.com --all

# 2. View current container state (detects both managed and unmanaged containers)
cstation docker status sg01.synercatalyst.com

# 3. Dry-run: see what would happen if you applied local configs
cstation docker plan sg01.synercatalyst.com

# 4. Deploy/Update: launch containers via SSH-based Compose orchestration
cstation docker apply sg01.synercatalyst.com --yes
```

## Advanced Features

### Fact Caching
To ensure the CLI feels snappy, `cstation` stores the latest hardware and performance metrics in a hidden `.facts.json` file inside each VPS directory.
- `vps list` displays these metrics in a "Live Metrics (Cached)" column.
- `vps status` displays them instantly and shows the age of the cache.
- Background tasks (or manual `-r` flags) keep the cache fresh.

### Schema Validation
Config files are strictly validated. If you have an error in your `vps.yaml`, you'll get a detailed report:
```text
✗ Schema validation failed for config/vps/sg01.synercatalyst.com/vps.yaml:
  - access.host: Field required
  - identity.region: Input should be a valid string
```

### Cloudflare DNS Management

Manage DNS records declaratively from `config/dns/` YAML files.

```bash
# List all Cloudflare DNS zones
cstation cloudflare zones

# Apply DNS records from config/dns/ to Cloudflare
cstation cloudflare apply example.com --yes
```

### GitHub & Odoo Management

```bash
# Setup SSH keys for GitHub access on a remote VPS (native SSH)
cstation github ssh sg01.synercatalyst.com --generate

# Download an Odoo database backup from a remote container
cstation odoo backup sg01.synercatalyst.com my-odoo-container my_db

# Restore a local Odoo backup zip to a remote VPS
cstation odoo restore sg01.synercatalyst.com target-container backup.zip
```

## Configuration

CStation loads configuration from these locations (highest precedence first):

1. `./etc/` — project-local
2. `/etc/cstation/` — system-wide
3. `~/.config/cstation/` — user-level

Provider tokens are optional and only needed for the initial `vps init` if using Cloud APIs:

```yaml
vps:
  default_provider: hetzner
  providers:
    hetzner:
      accounts:
        personal:
          token: "your-hetzner-token"
```

## VPS Config Structure

Each VPS has its own directory under `config/vps/` containing a main `vps.yaml` and fragment files:

```
config/vps/
├── sg01.synercatalyst.com/
│   ├── vps.yaml              ← infrastructure (access, facts, os)
│   ├── SG01_TRAEFIK.yaml     ← kind: Container
│   └── SG01_DB.yaml          ← kind: Container (PostgreSQL)
├── us02.synercatalyst.com/
│   ├── vps.yaml              ← infrastructure (access, facts, os)
│   ├── US02_traefik.yaml     ← kind: Container
│   └── US02_DB.yaml          ← kind: Container (PostgreSQL)
```

## Development

```bash
# Run all tests
uv run pytest -q

# Run CLI directly
uv run cstation vps list
```
