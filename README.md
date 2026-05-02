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

## Usage

### Basic Commands

```bash
cstation --version            # Show version
cstation <command> --help     # Get help for any command
```

### VPS Management

VPS commands follow a **"Local-First"** architecture, using your local `config/vps/` directory as the source of truth.

```bash
# List all managed VPS instances (shows CPU, RAM, Storage, and live Uptime)
cstation vps list

# Show live health dashboard via SSH (Load Avg, RAM, Disk, Docker status)
cstation vps status sg01.synercatalyst.com

# Initialize a per-VPS config via SSH scan (auto-discovers real IP and hardware)
cstation vps init sg01.synercatalyst.com --port 8288
cstation vps init 1.2.3.4 --user admin --key ~/.ssh/id_ed25519

# Initialize using Cloud Provider metadata (optional)
cstation vps init hetzner/myaccount:123456

# Dry-run: preview what would be applied
cstation vps plan eu01.synercatalyst.com

# Apply VPS configuration (OS hardening, swap, Docker setup, etc.)
cstation vps apply eu01.synercatalyst.com --yes

# Remove a VPS from local configuration
cstation vps remove eu01.synercatalyst.com
```

### Docker Service Management

Docker commands manage declarative container deployment via YAML fragments.

```bash
# Import running containers from VPS to local config
cstation docker import eu01.synercatalyst.com             # List available
cstation docker import eu01.synercatalyst.com my-app      # Import specific

# Plan: dry-run to see what would change
cstation docker plan eu01.synercatalyst.com

# Apply: deploy all enabled services
cstation docker apply eu01.synercatalyst.com --yes

# Status: show managed container state on VPS
cstation docker status eu01.synercatalyst.com
```

### Cloudflare DNS Management

Cloudflare commands manage DNS records declaratively from `config/dns/` YAML files.

```bash
# List all Cloudflare DNS zones
cstation cloudflare zones

# Apply DNS records from config/dns/ to Cloudflare
cstation cloudflare apply example.com --yes
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
│   ├── sg01-traefik.yaml     ← kind: Container
│   └── sg01-db.yaml          ← kind: Container
```

## Development

```bash
# Run all tests
uv run pytest -q

# Run CLI directly
uv run cstation vps list
```
