# Gemini Project Instructions: CStation

CStation is a DevOps CLI tool for managing VPS infrastructure, Docker container services, and deployments. It provides a declarative approach to server configuration and application deployment, wrapping SSH and cloud provider APIs in a Python-based orchestration layer.

## Project Overview

- **Purpose:** Automate VPS lifecycle management (OS hardening, Docker setup) and container service deployment.
- **Technologies:** Python 3.13, Typer (CLI), `uv` (Package Management), Fabric/Invoke (SSH), Pydantic (Models), YAML (Config), Rich (Terminal UI).
- **Core Architecture:**
  - `src/cstation/main.py`: Main entry point and command registration.
  - `src/cstation/commands/`: Command groups (vps, docker, netcup, github, cloudflare, server, pw).
  - `src/cstation/providers/`: Adapters for cloud providers (Hetzner, Vultr, Netcup) and Cloudflare DNS.
  - `src/cstation/providers/static.py`: Static provider for SSH-provisioned servers.
  - `src/cstation/ssh.py`: `SSHManager` wrapping Fabric for remote execution.
  - `src/cstation/config.py`: Configuration management.

## Building and Running

### Setup
```bash
# Install in editable mode
uv pip install -e .

# Install with test dependencies
uv pip install -e ".[test]"
```

### Running the CLI
```bash
# General usage
uv run cstation --help

# Example: List VPS instances
uv run cstation vps ls

# Example: Deploy containers to a VPS
uv run cstation docker apply eu01.synercatalyst.com
```

### Testing
- **Run all tests:** `uv run pytest -q`
- **Run single test:** `uv run pytest -q tests/commands/test_vps_cli.py`
- **Mocking Strategy:** 
  - Use `monkeypatch` to mock `SSHManager.run` with a dict of command → stdout responses.
  - Mock provider HTTP clients using `unittest.mock.Mock`.
  - Reset config between tests: call `_reset_config()` then `initialize_configuration()`.
  - For `apply` tests requiring confirmation, patch `typer.confirm`: `monkeypatch.setattr(typer, "confirm", lambda *a, **kw: True)`.

## Configuration Structure

CStation uses a hierarchical configuration system:
1. `./etc/` (Project-local)
2. `/etc/cstation/` (System-wide)
3. `~/.config/cstation/` (User-level)

### VPS Configuration (`config/vps/`)

Each VPS has a dedicated directory containing:
- `vps.yaml`: **Infrastructure declaration** (OS baseline, firewall, swap, Docker networks/daemons).
- `*.yaml` (Fragments): **Container/Stack declarations** (e.g., `traefik.yaml`, `portainer.yaml`).

### Command Separation
| Command | Scope | Reads |
|---------|-------|-------|
| `cstation vps apply` | OS + Docker infrastructure (Phases 1-13) | `vps.yaml` only |
| `cstation docker apply` | Container deployment | `vps.yaml` (for SSH) + fragment files |
| `cstation cloudflare plan/apply` | DNS record management | `config/dns/<domain>.yaml` |

### Cloudflare DNS Configuration (`config/dns/`)

Each domain has a YAML file in `config/dns/`:

```yaml
apiVersion: cstation/v1
kind: DNS
domain: example.com
records:
  - name: "@"
    type: A
    value: "1.2.3.4"
    ttl: 1
    proxied: false
  - name: "www"
    type: CNAME
    value: "example.com"
    ttl: 1
    proxied: true
```

Cloudflare API token is configured in `~/.config/cstation/config.yaml` under `cloudflare.api_token`.

## Development Conventions

### CLI Command Tree

```
cstation
├── version                          # Show version
├── init                             # Initialize configuration (--force, --backup, --dry-run, --developer)
├── server                           # Remote server management
│   ├── ssh                          # Setup SSH key authentication
│   ├── status                       # Check server status/health/uptime
│   ├── ls                           # List servers from inventory
│   ├── playbook                     # Ansible playbook management
│   │   ├── list                     # List available playbooks
│   │   └── push                     # Execute playbook on a host
│   ├── rm                           # Remove server from inventory
│   └── pw                           # PerfectWork sync operations
│       ├── sync                     # Sync PW files to remote server
│       ├── status                   # Check PW sync status
│       └── clean                    # Clean temp sync files
├── github                           # GitHub repository management
│   ├── ssh                          # Setup GitHub SSH keys
│   └── repo                         # Repository operations (list, sync, clone)
├── docker                           # Docker container service management
│   ├── plan                         # Dry-run: show container changes
│   ├── apply                        # Deploy container services
│   └── status                       # Show container state
├── vps                              # VPS lifecycle management
│   ├── ls                           # List VPS instances
│   ├── status                       # Show VPS status
│   ├── init                         # Initialize VPS config from provider
│   ├── plan                         # Dry-run: preview infrastructure changes
│   ├── apply                        # Apply VPS configuration (13 phases)
│   └── remove                       # Remove VPS from local config
├── netcup                           # Netcup SCP provider management
│   ├── auth-login                   # Authenticate via OAuth2 device-code flow
│   ├── auth-logout                  # Remove stored credentials
│   └── auth-show                    # Show authentication status
└── cloudflare                       # Cloudflare DNS management
    ├── zones                        # List all DNS zones
    ├── plan                         # Dry-run: show DNS drift
    └── apply                        # Apply DNS records to Cloudflare
```

### General
- **Python Version:** Strictly 3.13 (see `.python-version`).
- **Tooling:** Use `uv` for all dependency management.
- **No Linters:** Do not attempt to run `ruff`, `mypy`, or `pyright`.
- **Surgical Changes:** Maintain existing structure and patterns in `vps/main.py` and `docker/main.py`.

### Adding New Components
- **Command Groups:** Create `src/cstation/commands/<group>/main.py` and register in `src/cstation/main.py`.
- **Providers:** Implement `VPSProvider` protocol in `src/cstation/providers/<name>.py` and register in `vps/main.py`.

### Netcup SCP Field Mapping
| VPS field | SCP source |
|-----------|-----------|
| `id` | `server["id"]` |
| `status` | `server["serverLiveInfo"]["state"]` (RUNNING→running, etc.) |
| `ipv4` | `server["ipv4Addresses"][0]["ip"]` |
| `vcpu` | `server["serverLiveInfo"]["cpuCount"]` |
| `memory_mb` | `server["serverLiveInfo"]["maxServerMemoryInMiB"]` |
| `disk_gb` | Sum of `server["serverLiveInfo"]["disks"][*]["capacityInMiB"]` / 1024 |

### Static Provider (SSH)

The `static` provider is used for servers without a cloud provider API. It uses SSH to connect and retrieve VPS facts.

```bash
# Initialize a VPS config from SSH (no cloud provider needed)
cstation vps init static/SSH:your-server.com
cstation vps init static/SSH:192.168.1.100 --user admin --port 2222 --key ~/.ssh/id_ed25519
```

Key differences from cloud providers:
- No API token required; uses SSH to gather facts
- Target format: `static/SSH:<hostname_or_IP>`
- `vps ls` discovers statically-provisioned VPS by scanning `config/vps/*/vps.yaml` for `identity.provider: static`
- Cannot create or delete VPS instances

## Infrastructure & Services Notes

### VPS YAML Schema (`kind: VPS`)
```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region, provider }
access: { host, user, port, key }
facts: { os, cpu, memory, disks, network, hostname, packages }
os:
  baseline: { upgrade_all, packages, shell, terminal, swap: { size_gb }, tuning, sshd, fail2ban, firewall }
docker:
  daemon: { log_driver, log_opts, storage_driver, live_restore, iptables }
  networks: [PW_NET]
  directories: [/var/lib/perfectwork]
```

### Container Fragment Schema (`kind: Container`)
```yaml
apiVersion: cstation/v1
kind: Container
name: myapp
enabled: true
image: myapp:latest
container_name: EU01_myapp   # Optional: explicit Docker container name
network: PW_NET
ports: ["80:80"]
volumes: ["/data:/app/data"]
env: { KEY: VAL }                      # Non-secret (committed)
env_file: .env                         # Secrets loaded from .env file on VPS
secrets: [DB_PASSWORD]                 # Secret keys (written to .env on VPS only)
restart_policy: unless-stopped          # Optional: Docker restart policy
command: ["--configFile=/etc/traefik/traefik.yml"]  # Optional: Docker compose command override
owner: "1000:1000"                     # Optional: chown -R after apply (uid:gid)
subdirs: [etc, conf, data]             # Optional: override service subdirectories
traefik:                               # Optional: dynamic routing config
  http:
    routers:
      myapp:
        rule: "Host(`...`)"
        entryPoints: [websecure]
        service: myapp
        tls:
          certResolver: le_dns_resolver
    services:
      myapp:
        loadBalancer:
          serverPort: 3000
static_config: {...}                   # Optional: service-specific static config
```

### Traefik v3 Pitfalls (IMPORTANT)
- **TCP Services:** Must use `address` (e.g., `host:port`), NOT `url`.
- **Proxy Protocol:** Use `tcp.serversTransports` instead of the deprecated `proxyProtocol` on the load balancer.
- **File Provider:** Dynamic config is written to `/var/lib/traefik/conf/<service_name>.yml`. Traefik watches this for changes.

### Key Files for Reference
- `pyproject.toml`: Dependencies and entry points.
- `src/cstation/main.py`: CLI entry point and command registration.
- `src/cstation/commands/vps/main.py`: Core VPS orchestration logic.
- `src/cstation/commands/docker/services/base.py`: Base classes for container deployment.
- `src/cstation/providers/cloudflare.py`: Cloudflare DNS provider adapter.
- docs/PW_CS/: Legacy reference (bash/ansible scripts).
