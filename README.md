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

# Initialize a VPS config from SSH (no cloud provider needed)
uv run cstation vps init static/SSH:your-server.com
uv run cstation vps init static/SSH:192.168.1.100 --user admin --port 2222 --key ~/.ssh/id_ed25519
```

## Usage

### Basic Commands

```bash
cstation version              # Show version
cstation init                 # Initialize configuration (requires sudo)
cstation init --developer     # Initialize with user ownership (no sudo for editing)
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
cstation vps init netcup/default:v2202604354651455383
cstation vps init static/SSH:your-server.com
cstation vps init static/SSH:192.168.1.100 --user admin --port 2222 --key ~/.ssh/id_ed25519

# Dry-run: preview what would be applied
cstation vps plan eu01.synercatalyst.com

# Apply VPS configuration (13 phases: upgrade, packages, shell, terminal, sshd, firewall, swap, tuning, fail2ban, hostname, docker_daemon, docker_networks, docker_directories)
cstation vps apply eu01.synercatalyst.com
cstation vps apply eu01.synercatalyst.com --yes
cstation vps apply eu01.synercatalyst.com --phase packages

# Remove a VPS from local configuration (does NOT destroy the VPS on the cloud provider)
cstation vps remove eu01.synercatalyst.com
cstation vps remove eu01.synercatalyst.com --yes
cstation vps remove eu01.synercatalyst.com --skip-check  # Skip SSH check if server is unreachable
```

VPS command targets use the format `<provider>/<account>:<id>`. Examples:
- `hetzner/myaccount:123456` — Hetzner server by numeric ID
- `vultr/main:3431427c-9755-4064-903e-7a3e8bc82791` — Vultr instance by UUID
- `netcup/default:v2202604354651455383` — Netcup server by name (OAuth2 auth required)
- `static/SSH:your-server.com` — Any server via SSH (no cloud provider API needed)

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
cstation github ssh             # Setup GitHub SSH keys on a remote server
cstation github ssh hostname --generate --add-to-github  # Generate key and add to GitHub
cstation github repo list       # List repositories
cstation github repo sync repo  # Sync a repository
cstation github repo clone repo # Clone a repository
```

### Server Management

Server commands manage remote servers via Ansible and direct SSH.

```bash
# Setup SSH key authentication for a remote server
cstation server ssh hostname
cstation server ssh hostname --generate           # Generate key if missing
cstation server ssh hostname -k ~/.ssh/id_ed25519 # Use specific key

# Check server status, health, and uptime
cstation server status
cstation server status hostname --services --no-uptime

# List servers from Ansible inventory
cstation server ls
cstation server ls hostname   # Show details for specific server

# Remove a server entry from the Ansible inventory
cstation server rm server_name --force

# Ansible playbook management
cstation server playbook list                    # List available playbooks
cstation server playbook push playbook host      # Execute a playbook on a host

# PerfectWork sync operations
cstation server pw sync hostname 18.0            # Sync PW files to server
cstation server pw sync hostname 18.0 --port 8288 --dry-run
cstation server pw status hostname 18.0          # Check sync status
cstation server pw clean --all                    # Clean temp sync files
```

### Cloudflare DNS Management

Cloudflare commands manage DNS records declaratively from `config/dns/` YAML files.

```bash
# List all Cloudflare DNS zones
cstation cloudflare zones

# Dry-run: compare local DNS config against Cloudflare and show drift
cstation cloudflare plan
cstation cloudflare plan example.com

# Apply DNS records from config/dns/ to Cloudflare
cstation cloudflare apply
cstation cloudflare apply example.com --yes
cstation cloudflare apply example.com --yes --delete  # Also delete unmanaged records
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
container_name: EU01_traefik   # Optional: explicit Docker container name
network: PW_NET
ports: ["80:80"]
volumes: [...]
env: {...}                      # non-secret config → compose environment
env_file: .env                   # secrets loaded from .env file on VPS
secrets: [...]                  # secret key names → .env on VPS only (NOT committed)
restart_policy: unless-stopped  # Optional: Docker restart policy
command: ["--configFile=/etc/traefik/traefik.yml"]  # Optional: Docker compose command override
owner: "1000:1000"              # Optional: chown -R after apply (uid:gid)
subdirs: [etc, conf, data]      # Optional: override service subdirectories
static_config: {...}            # Optional: service-specific static config
traefik:                        # Optional: dynamic routing config
  http:
    routers:
      myapp:
        rule: "Host(`myapp.example.com`)"
        entryPoints: [websecure]
        service: myapp
        tls:
          certResolver: le_dns_resolver
    services:
      myapp:
        loadBalancer:
          serverPort: 3000
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
│   ├── server/          # Remote server management (ssh, status, ls, playbook, rm, pw)
│   ├── github/          # GitHub repository operations (ssh, repo)
│   ├── docker/
│   │   ├── main.py      # Docker commands: plan, apply, status
│   │   ├── services/    # Service classes (TraefikService, PortainerService, etc.)
│   │   └── compose/     # Compose file rendering, .env writer
│   ├── vps/             # VPS lifecycle (ls, status, init, plan, apply, remove)
│   ├── netcup/          # Netcup SCP authentication (auth-login, auth-logout, auth-show)
│   ├── cloudflare/      # Cloudflare DNS management (zones, plan, apply)
│   └── pw/              # PerfectWork sync operations (sync, status, clean)
├── providers/
│   ├── base.py          # VPSProvider protocol + VPS/VPSStatus models
│   ├── cloudflare.py   # Cloudflare DNS provider adapter
│   ├── static.py        # Static provider for SSH-provisioned servers
│   ├── hetzner.py       # Hetzner Cloud adapter
│   ├── vultr.py         # Vultr adapter
│   ├── netcup.py        # Netcup SCP REST API adapter
│   ├── netcup_auth.py   # Netcup OAuth2 device-code flow
│   └── errors.py        # Provider error classes
config/
├── dns/                 # Cloudflare DNS config files (<domain>.yaml)
└── vps/                 # Per-VPS config directories
    └── <vps-name>/
        ├── vps.yaml
        ├── <CONTAINER_NAME>_traefik.yaml
        └── ...
tests/
├── commands/
│   ├── test_vps_cli.py      # VPS CLI integration tests
│   └── test_docker_cli.py   # Docker CLI tests
└── providers/
    ├── test_hetzner.py       # Hetzner adapter tests
    ├── test_vultr.py         # Vultr adapter tests
    └── test_netcup.py        # Netcup adapter tests
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
| Static | SSH key (CLI flags) | None needed (uses `--user`, `--port`, `--key`) | No | No |

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