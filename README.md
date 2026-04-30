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
# Initialize system configuration
sudo cstation init

# Initialize with user ownership (allows editing without sudo)
sudo cstation init --developer

# List VPS instances
uv run cstation vps ls

# Initialize a VPS config from a Hetzner server
uv run cstation vps init hetzner/myaccount:123456

# Initialize a VPS config from a Netcup server
cstation netcup auth-login         # First-time: authenticate with Netcup SCP
uv run cstation vps init netcup/default:v2202604354651455383
```

## Usage

### Basic Commands

```bash
cstation version              # Show version
cstation init                 # Initialize configuration
cstation <command> --help     # Get help for any command
```

### VPS Management

VPS commands manage OS + Docker infrastructure on remote servers.

```bash
# List VPS instances across all configured providers
cstation vps ls
cstation vps ls --provider hetzner

# Show VPS status (supports provider/account:id format)
cstation vps status hetzner/myaccount:123456
cstation vps status myaccount:123456

# Initialize a per-VPS config from provider metadata + SSH facts
cstation vps init hetzner/myaccount:123456

# Dry-run: preview what would be applied
cstation vps plan eu01.synercatalyst.com

# Apply VPS configuration (13 phases: upgrade, packages, shell, terminal, sshd, firewall, swap, tuning, fail2ban, hostname, docker_daemon, docker_networks, docker_directories)
cstation vps apply eu01.synercatalyst.com
cstation vps apply eu01.synercatalyst.com --yes
cstation vps apply eu01.synercatalyst.com --phase packages
```

VPS command targets use the format `<provider>/<account>:<id>`. Examples:
- `hetzner/myaccount:123456` — Hetzner server by numeric ID
- `vultr/main:3431427c-9755-4064-903e-7a3e8bc82791` — Vultr instance by UUID
- `netcup/default:v2202604354651455383` — Netcup server by name (OAuth2 auth required)

### Netcup SCP Authentication

Netcup uses OAuth2 device-code flow (browser-based) instead of API tokens:

```bash
cstation netcup auth-login    # Start OAuth2 flow (opens browser)
cstation netcup auth-logout   # Revoke and remove stored credentials
cstation netcup auth-show     # Show credential status
```

Credentials are stored in `~/.config/cstation/netcup-oauth.json` (refresh token, mode 0600).

### Docker Service Management

Docker commands manage container deployment on VPS servers where `cstation vps apply` has already been run.

```bash
# Plan: dry-run to see what would change
cstation docker plan eu01.synercatalyst.com
cstation docker plan eu01.synercatalyst.com --service traefik

# Apply: deploy all enabled services
cstation docker apply eu01.synercatalyst.com
cstation docker apply eu01.synercatalyst.com --service traefik
cstation docker apply eu01.synercatalyst.com --yes
cstation docker apply eu01.synercatalyst.com --prune

# Status: show container state on VPS
cstation docker status eu01.synercatalyst.com
```

### GitHub Management

```bash
cstation github --help
cstation github ssh             # Setup GitHub SSH keys
cstation github repo            # Repository operations
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
    netcup:
      scp:
        default:
          enabled: true
```

## VPS Config Structure

Each VPS has its own directory under `config/vps/` containing a main `vps.yaml` and optional fragment files:

```
config/vps/
├── eu01.synercatalyst.com/
│   ├── vps.yaml              ← identity, access, facts, os, docker infrastructure
│   ├── EU01_traefik.yaml     ← kind: Container
│   ├── EU01_portainer.yaml   ← kind: Container
│   └── EU01_stalwart.yaml    ← kind: Container (email server)
├── us02.synercatalyst.com/
│   ├── vps.yaml
│   ├── US02_traefik.yaml
│   ├── US02_portainer.yaml
│   └── US02_stalwart.yaml
├── sg07.ansis.com.sg/
│   ├── vps.yaml
│   └── ...
```

- `vps.yaml` — read by `cstation vps` commands (infrastructure only)
- Fragment files (`*.yaml` except `vps.yaml`) — read by `cstation docker` commands (container deployment)

Fragment filenames can use any naming convention, but it's recommended to match the `container_name` field (e.g., `US02_traefik.yaml`, `US02_portainer.yaml`) for easy searching.

### Fragment: kind: Container

Cstation generates the compose file from the fragment config:

```yaml
apiVersion: cstation/v1
kind: Container
name: traefik
enabled: true
image: traefik:latest
network: PW_NET
ports: [...]
volumes: [...]
env: {...}          # non-secret config → compose environment
env_file: .env      # secrets loaded from .env file on VPS
secrets: [...]      # secret key names → .env on VPS only (NOT committed)
restart_policy: unless-stopped
static_config: {...}  # optional, service-specific
```

### Fragment: kind: Stack

Cstation clones a git repo and patches it:

```yaml
apiVersion: cstation/v1
kind: Stack
name: mailcow
enabled: false
git_repo: "https://github.com/mailcow/mailcow-dockerized"
git_branch: master
git_dir: /opt/mailcow
network: PW_NET
env: {...}
```

### Secrets

- **Non-secret config** → fragment `env` section (committed to git, written as compose `environment`)
- **Secrets** → fragment `secrets` section lists key names; values go in `.env` on VPS only (NOT committed)
- On first `docker apply`: cstation writes a `.env` template with placeholder values. SSH into the VPS to set real values.
- On subsequent applies: cstation preserves existing `.env` files.

## Command Separation

| Command | Scope | Reads | Does NOT do |
|---------|-------|-------|-------------|
| `cstation vps apply` | OS + Docker infrastructure (phases 1-13) | `vps.yaml` only | Deploy any containers |
| `cstation docker apply` | Deploy container services | `vps.yaml` (for SSH) + fragment files | Touch OS/Docker infrastructure |

Dependency: `vps apply` must run first (installs Docker, creates `PW_NET`). Then `docker apply` deploys containers.

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
├── commands/
│   ├── version/         # Version command
│   ├── init/            # Initialization command
│   ├── github/          # GitHub repository operations
│   ├── docker/
│   │   ├── main.py      # Docker commands: plan, apply, status
│   │   ├── services/    # Service classes (TraefikService, PortainerService, etc.)
│   │   └── compose/     # Compose file rendering, .env writer
│   ├── vps/             # VPS lifecycle (ls, status, init, plan, apply)
│   ├── netcup/          # Netcup SCP authentication (auth-login, auth-logout, auth-show)
│   ├── pw/              # PerfectWork operations
│   └── sync/            # Sync management
├── providers/
│   ├── base.py          # VPSProvider protocol + VPS/VPSStatus models
│   ├── hetzner.py       # Hetzner Cloud adapter
│   ├── vultr.py         # Vultr adapter
│   ├── netcup.py        # Netcup SCP REST API adapter
│   ├── netcup_auth.py   # Netcup OAuth2 device-code flow
│   └── errors.py        # Provider error classes
tests/
├── commands/
│   ├── test_vps_cli.py  # VPS CLI integration tests
│   └── test_docker_cli.py  # Docker CLI tests
├── providers/
│   ├── test_hetzner.py  # Hetzner adapter tests
│   ├── test_vultr.py    # Vultr adapter tests
│   └── test_netcup.py  # Netcup adapter tests
config/
└── vps/                 # Per-VPS config directories
    └── <vps-name>/
        ├── vps.yaml
        ├── <CONTAINER_NAME>_traefik.yaml
        └── ...
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
2. For OAuth2-based providers (like Netcup), create `src/cstation/providers/<name>_auth.py` for the auth flow
3. Add to `_provider_from_token()` and `_resolve_account()` in `src/cstation/commands/vps/main.py`
4. For OAuth2 providers, add auth commands in `src/cstation/commands/<name>/main.py` and register in `src/cstation/main.py`

#### Provider comparison

| Provider | Auth method | Config format | VPS creation | VPS deletion |
|----------|------------|---------------|-------------|-------------|
| Hetzner | API token | `accounts.<name>.token` | Yes | Yes |
| Vultr | API token | `accounts.<name>.token` | No | Yes |
| Netcup | OAuth2 device-code | `scp.<name>.enabled` | No | No |

## Troubleshooting

### No VPS providers configured

Set provider tokens in `~/.config/cstation/config.yaml` or set `HETZNER_TOKEN` environment variable. For Netcup, run `cstation netcup auth-login` first.

### Command not found

```bash
uv pip install -e .
uv run cstation --help
```

### Tests failing

```bash
uv pip install -e ".[test]"
uv run pytest -q
```