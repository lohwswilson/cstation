# CStation - Infrastructure Management CLI

A DevOps CLI tool for managing infrastructure, VPS lifecycle, and deployments. Built with Python 3.13, Typer, and uv.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
git clone <repository-url>
cd cstation

# Install in editable mode
uv pip install -e .

# Verify
uv run cstation --help
```

Install with test dependencies:

```bash
uv pip install -e ".[test]"
```

## Quick Start

```bash
# Initialize system configuration
sudo cstation init

# Initialize with user ownership (allows editing without sudo)
sudo cstation init --developer

# List VPS instances
uv run cstation vps ls

# Initialize a VPS config from a Hetzner server
uv run cstation vps init hetzner/myaccount:123456
```

## Usage

### Basic Commands

```bash
cstation version              # Show version
cstation init                 # Initialize configuration
cstation <command> --help     # Get help for any command
```

### VPS Management

```bash
# List VPS instances across all configured providers
cstation vps ls
cstation vps ls --provider hetzner

# Show VPS status (supports provider/account:id format)
cstation vps status hetzner/myaccount:123456
cstation vps status myaccount:123456

# Initialize a per-VPS config from provider metadata + SSH facts
cstation vps init hetzner/myaccount:123456
cstation vps init hetzner/myaccount:123456 --out config/vps/sg05.yaml

# Dry-run: preview what would be applied
cstation vps plan config/vps/sg05.yaml

# Apply VPS configuration (upgrade, packages, shell, terminal, sshd, firewall)
cstation vps apply config/vps/sg05.yaml
cstation vps apply config/vps/sg05.yaml --yes
cstation vps apply config/vps/sg05.yaml --phase packages
```

VPS command targets use the format `<provider>/<account>:<id>`. Examples:
- `hetzner/myaccount:123456` — Hetzner server by numeric ID
- `vultr/main:3431427c-9755-4064-903e-7a3e8bc82791` — Vultr instance by UUID

### Server Management

```bash
cstation server ls              # List servers
cstation server status <host>   # Check server status
cstation server ssh <host>     # Setup SSH key authentication
cstation server push <playbook> <target>  # Execute playbook
cstation server rm <host>      # Remove server from inventory
```

### GitHub Management

```bash
cstation github --help
cstation github ssh             # Setup GitHub SSH keys
cstation github repo            # Repository operations
```

### Docker Management

```bash
cstation docker --help
```

## Configuration

CStation loads configuration from these locations (highest precedence first):

1. `./etc/` — project-local
2. `/etc/cstation/` — system-wide
3. `~/.config/cstation/` — user-level

Provider tokens for VPS commands are configured in `~/.config/cstation/config.yaml`:

```yaml
vps:
  default_provider: hetzner
  providers:
    hetzner:
      accounts:
        personal:
          token: "your-hetzner-token"
        work:
          token: "your-work-hetzner-token"
    vultr:
      accounts:
        main:
          token: "your-vultr-token"
```

VPS init writes per-VPS config files to `config/vps/<name>.yaml` by default (e.g. `config/vps/sg05.yaml`).

## Development

```bash
# Run all tests
uv run pytest -q

# Run a specific test
uv run pytest -q tests/commands/test_vps_cli.py::test_vps_init_writes_yaml

# Run CLI directly
uv run cstation vps ls
```

### Project Structure

```
src/cstation/
├── main.py              # CLI entry point (Typer app)
├── config.py            # Configuration management (ConfigManager)
├── ssh.py               # SSH remote execution (Fabric wrapper)
├── inventory.py         # Inventory management
├── commands/
│   ├── version/         # Version command
│   ├── init/            # Initialization command
│   ├── server/          # Ansible-based server management
│   ├── github/          # GitHub repository operations
│   ├── docker/          # Docker management
│   ├── vps/             # VPS lifecycle (ls, status, init, plan, apply)
│   ├── pw/              # PerfectWork operations
│   └── sync/            # Sync management
├── providers/
│   ├── base.py          # VPSProvider protocol + VPS/VPSStatus models
│   ├── hetzner.py       # Hetzner Cloud adapter
│   ├── vultr.py         # Vultr adapter
│   └── errors.py        # Provider exceptions
tests/
├── commands/
│   └── test_vps_cli.py  # VPS CLI integration tests
├── providers/
│   ├── test_models.py   # Provider model tests
│   ├── test_hetzner.py  # Hetzner adapter tests
│   └── test_vultr.py    # Vultr adapter tests
config/
└── vps/                 # Per-VPS config YAML files
```

### Adding a New Command Group

1. Create `src/cstation/commands/<group>/__init__.py` (empty)
2. Create `src/cstation/commands/<group>/main.py` with a Typer app
3. Register in `src/cstation/main.py`:
   ```python
   from cstation.commands.<group>.main import <group>_app
   app.add_typer(<group>_app, name="<group>")
   ```

### Adding a New Provider

1. Create `src/cstation/providers/<name>.py` implementing `VPSProvider` protocol from `base.py`
2. Add to `_provider_from_token()` in `src/cstation/commands/vps/main.py`

## Troubleshooting

### No VPS providers configured

Set provider tokens in `~/.config/cstation/config.yaml` (see Configuration above) or set `HETZNER_TOKEN` environment variable.

### Command not found

```bash
# Reinstall in editable mode
uv pip install -e .
uv run cstation --help
```

### Tests failing

```bash
# Ensure test dependencies are installed
uv pip install -e ".[test]"
uv run pytest -q
```