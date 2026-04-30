# Docker Service Management (Design)

## Summary

CStation manages Docker service lifecycle on remote VPS hosts via SSH + `docker compose`. Container declarations live in separate fragment files under the VPS config directory. This replaces the old Ansible-based `cstation docker playbook` system with a consistent SSH-based approach.

**VPS config structure** (one directory per VPS):
```
config/vps/<vps-name>/
├── vps.yaml              ← identity, access, facts, os, docker infrastructure
├── traefik.yaml          ← kind: Container
├── portainer.yaml        ← kind: Container
└── mailcow.yaml          ← kind: Stack
```

**Command separation**: `cstation vps apply` handles OS + Docker infrastructure only. `cstation docker apply` handles container deployment only.

The primary workflow: edit fragment files → `cstation docker plan <vps>` → `cstation docker apply <vps>`.

## Goals

- Full container lifecycle via SSH: deploy, start, stop, restart, remove, upgrade.
- Declarative fragment files — `plan` shows drift, `apply` converges.
- Per-service compose files on the VPS — each service is independently deployable and upgradeable.
- All services on the `PW_NET` network for Traefik routing.
- Built-in service templates for common stacks (Traefik, Mailcow, Portainer, PostgreSQL, n8n, Odoo).
- Extensible: new service types added as Python classes, not config files.
- Retire the Ansible-based `cstation docker playbook` commands.
- Clean separation from `cstation vps apply` — no container logic in VPS apply.

## Non-Goals (MVP)

- Automatic container health monitoring or auto-restart policies (Docker handles restart policies).
- Multi-VPS container orchestration.
- Container image building (pull from registry only in MVP).
- Secret rotation or vault integration (`.env` files on the VPS for now).
- Docker Swarm or Kubernetes orchestration.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime | `docker compose` (v2) | Already installed (`docker-compose-v2`), declarative, idempotent `up -d` |
| Config location | Fragment files in VPS config directory | One file per service; independent lifecycle; clean git diffs |
| VPS config directory | `config/vps/<vps-name>/vps.yaml` + fragments | Directory = VPS; `vps.yaml` = infrastructure; fragments = containers |
| Fragment naming | Service name (`traefik.yaml`, `portainer.yaml`) | Simple, matches service identity |
| Fragment kind | `Container` or `Stack` | `Container` = cstation generates compose; `Stack` = clone git repo + patch |
| CLI argument | Directory path or VPS name | `cstation docker apply eu01.synercatalyst.com` or full path |
| Compose file placement on VPS | `/var/lib/<service>/docker-compose.yml` | Infrastructure services at `/var/lib/<service>/`; Odoo at `/var/lib/perfectwork/` |
| Network | All services on `PW_NET` | Traefik is on `PW_NET` and routes all traffic |
| Service isolation | One compose file per service | Independent lifecycle, easier upgrades, standard pattern |
| Apply approach | SSH + `docker compose up -d` | No Ansible dependency; same pattern as `cstation vps apply` |
| Old playbook system | Retire | Replaced by declarative SSH-based approach |
| Templates | Simple Python string templates | Start simple; graduate to Jinja2 only if needed |
| Image tags | `latest` by default | User pins version in fragment YAML if desired |
| Pre-flight check | Verify Docker + PW_NET before apply | Prevent confusing errors if `vps apply` hasn't been run |
| Directory creation | `docker apply` creates its own dirs | Simpler workflow than requiring `vps apply` to pre-create service dirs |
| Service ordering | Implicit for built-in services | Traefik first; `depends_on` only for custom services later |

## VPS Config Structure

Each VPS has its own directory under `config/vps/`. The main file is always `vps.yaml`. Fragment files declare containers and stacks.

### Directory Layout (Local Repository)

```
config/vps/
├── eu01.synercatalyst.com/
│   ├── vps.yaml              ← kind: VPS (identity, access, facts, os, docker)
│   ├── traefik.yaml          ← kind: Container
│   ├── portainer.yaml        ← kind: Container
│   └── mailcow.yaml          ← kind: Stack (enabled: false)
├── sg07.ansis.com.sg/
│   ├── vps.yaml
│   ├── traefik.yaml
│   └── ...
```

### `vps.yaml` — Main VPS File

Contains everything `cstation vps apply` needs. **No `containers` section** — that's handled by fragments.

```yaml
apiVersion: cstation/v1
kind: VPS
identity:
  name: eu01.synercatalyst.com
  stage: prod
  region: hel1
access:
  host: 37.27.218.255
  user: root
  port: 22
facts:
  os: { id: ubuntu, version: "24.04", ... }
  cpu: { ... }
  memory: { ... }
  disks: [ ... ]
  network: { ... }
  hostname: EU01
  packages: { detected: [...], missing: [...] }
os:
  hostname: eu01.synercatalyst.com
  baseline:
    upgrade_all: true
    packages: [fail2ban, docker.io, containerd, docker-compose-v2, zsh]
    shell: zsh
    terminal: xterm-256color
    swap: { size_gb: 4 }
    tuning: { ... }
    sshd: { disable_password_auth: true }
    fail2ban: { bantime: 1h, findtime: 10m, maxretry: 5 }
    firewall: { mode: ufw, allow: [22/tcp, 80/tcp, 443/tcp, 25/tcp, 465/tcp, 587/tcp, 993/tcp, 995/tcp] }
  journald: { system_max_use: 500M, forward_to_syslog: false }
docker:
  daemon:
    log_driver: json-file
    log_opts: { max_size: 10m, max_file: "3" }
    storage_driver: overlay2
    live_restore: true
    iptables: true
  networks: [PW_NET]
  directories: [/var/lib/perfectwork]
```

### Fragment: `kind: Container`

Used for services where cstation generates the compose file entirely from the fragment config.

```yaml
# config/vps/eu01.synercatalyst.com/traefik.yaml
apiVersion: cstation/v1
kind: Container
name: traefik
enabled: true
image: traefik:latest
network: PW_NET
ports:
  - "80:80"
  - "443:443"
  - "25:25"
  - "465:465"
  - "587:587"
  - "993:993"
  - "995:995"
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
  - /var/lib/traefik/letsencrypt:/letsencrypt
  - /var/lib/traefik/conf:/etc/traefik/conf
  - /var/lib/traefik/etc/traefik.yml:/etc/traefik/traefik.yml:ro
  - /var/lib/traefik/logs:/etc/traefik/logs
env_file: .env
env:
  DHPARAM_GENERATION: "false"
secrets:
  - CF_API_EMAIL
  - CF_API_KEY
restart_policy: unless-stopped
static_config:
  global:
    checknewversion: false
    sendanonymoususage: false
  entryPoints:
    web:
      address: ":80"
      http:
        redirections:
          entryPoint:
            to: websecure
            scheme: https
            permanent: true
      forwardedHeaders:
        insecure: true
    websecure:
      address: ":443"
      forwardedHeaders:
        insecure: true
    smtp:
      address: ":25"
    submissions:
      address: ":465"
    submission:
      address: ":587"
    imaps:
      address: ":993"
    pop3s:
      address: ":995"
  providers:
    docker:
      endpoint: "unix:///var/run/docker.sock"
      exposedByDefault: false
      network: PW_NET
      watch: true
    file:
      directory: "/etc/traefik/conf"
      watch: true
  certificatesResolvers:
    le_resolver:
      acme:
        email: "syner.catalyst@gmail.com"
        storage: "/letsencrypt/acme.json"
        caServer: "https://acme-v02.api.letsencrypt.org/directory"
        keyType: EC256
        tlsChallenge: {}
    le_dns_resolver:
      acme:
        email: "syner.catalyst@gmail.com"
        storage: "/letsencrypt/acme_dns.json"
        caServer: "https://acme-v02.api.letsencrypt.org/directory"
        keyType: EC256
        dnsChallenge:
          provider: cloudflare
          delayBeforeCheck: 15s
          resolvers:
            - "1.1.1.1:53"
            - "1.0.0.1:53"
  api:
    dashboard: true
  log:
    level: INFO
    filePath: "/etc/traefik/logs/traefik.log"
    format: json
  accessLog:
    filePath: "/etc/traefik/logs/access.log"
    format: json
    bufferingSize: 100
  metrics:
    prometheus:
      addEntryPointsLabels: true
      addServicesLabels: true
```

```yaml
# config/vps/eu01.synercatalyst.com/portainer.yaml
apiVersion: cstation/v1
kind: Container
name: portainer
enabled: true
image: portainer/portainer-ce:latest
container_name: EU01_portainer
network: PW_NET
ports:
  - "9000:9000"
  - "9443:9443"
  - "8000:8000"
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /var/lib/portainer/data:/data
env:
  PORTAINER_LOG_LEVEL: INFO
restart_policy: always
```

### Fragment: `kind: Stack`

Used for services that ship their own `docker-compose.yml` in a git repo. Cstation clones the repo and patches it.

```yaml
# config/vps/eu01.synercatalyst.com/mailcow.yaml
apiVersion: cstation/v1
kind: Stack
name: mailcow
enabled: false
git_repo: "https://github.com/mailcow/mailcow-dockerized"
git_branch: master
git_dir: /opt/mailcow
network: PW_NET
env:
  SKIP_LETS_ENCRYPT: "y"
  SKIP_NGINX: "y"
  HTTP_PORT: "8082"
  HTTPS_PORT: "8443"
  MAILCOW_HOSTNAME: "mail.synercatalyst.com"
  TZ: "UTC"
```

### Fragment Schema Rules

| Field | `kind: Container` | `kind: Stack` | Notes |
|-------|--------------------|--------------|-------|
| `apiVersion` | required | required | Always `cstation/v1` |
| `kind` | `Container` | `Stack` | Determines how cstation processes the fragment |
| `name` | required | required | Service name; matches fragment filename by convention |
| `enabled` | required | required | `true`/`false` — controls whether plan/apply considers it |
| `image` | required | — | Docker image (e.g., `traefik:latest`) |
| `container_name` | optional | — | Docker container name (e.g., `EU01_portainer`). Default: service `name` |
| `network` | required | required | Docker network (defaults to `PW_NET`) |
| `ports` | optional | — | Host port bindings (list of Docker port spec strings) |
| `volumes` | optional | optional | Volume mount specifications |
| `env` | optional | optional | Non-secret environment variables (written as compose `environment`) |
| `env_file` | optional | — | Path to `.env` file for secrets (written as compose `env_file`) |
| `secrets` | optional | optional | List of secret key names — written to `.env` on VPS only (NOT committed) |
| `ulimits` | optional | — | Container ulimits (e.g., `nofile: {soft: 65536, hard: 65536}`) |
| `restart_policy` | optional | — | Default: `unless-stopped` |
| `static_config` | optional | — | Service-specific config written as a file (e.g., Traefik's `traefik.yml`) |
| `git_repo` | — | required | Git repository URL |
| `git_branch` | — | optional | Git branch (default: `master`) |
| `git_dir` | — | required | Clone destination on VPS |

### Fragment Discovery

```python
def _load_vps_config(vps_dir: Path) -> dict:
    """Load the main VPS config from a directory or resolve by VPS name."""
    if not vps_dir.is_dir():
        # Try treating argument as VPS name → search in config/vps/
        vps_dir = Path("config/vps") / str(vps_dir)
    main = vps_dir / "vps.yaml"
    if not main.exists():
        raise FileNotFoundError(f"No vps.yaml in {vps_dir}")
    with main.open() as f:
        return yaml.safe_load(f)

def _discover_fragments(vps_dir: Path) -> list[Path]:
    """Discover container/stack fragment files for a VPS."""
    return sorted(p for p in vps_dir.glob("*.yaml") if p.name != "vps.yaml")
```

### Directory Convention on VPS

Infrastructure services (Traefik, Portainer, etc.) store data under `/var/lib/<service>/`. The Odoo/PerfectWork directory (`/var/lib/perfectwork/`) is reserved for Odoo instances.

| Service | Local fragment | VPS compose directory | VPS data directory |
|---------|---------------|----------------------|-------------------|
| Traefik | `traefik.yaml` | `/var/lib/traefik/` | `/var/lib/traefik/letsencrypt/`, `/var/lib/traefik/conf/` |
| Portainer | `portainer.yaml` | `/var/lib/portainer/` | `/var/lib/portainer/data/` |
| Mailcow | `mailcow.yaml` | `/opt/mailcow/` (git clone) | `/opt/mailcow/data/` |
| Odoo | `odoo-aim.yaml` | `/var/lib/perfectwork/...` | `/var/lib/perfectwork/...` |

## CLI Commands

### CLI Argument Resolution

The `<vps>` argument accepts both a directory path and a VPS name:

```bash
# By directory path (explicit)
uv run cstation docker plan config/vps/eu01.synercatalyst.com
uv run cstation docker apply config/vps/eu01.synercatalyst.com

# By VPS name (auto-discover in config/vps/)
uv run cstation docker plan eu01.synercatalyst.com
uv run cstation docker apply eu01.synercatalyst.com
```

The same resolution applies to `cstation vps plan/apply`.

### Command Reference

```bash
# Plan/apply
uv run cstation docker plan <vps>                                    # Dry-run all enabled services
uv run cstation docker plan <vps> --service traefik                  # Dry-run single service
uv run cstation docker apply <vps>                                   # Deploy all enabled services
uv run cstation docker apply <vps> --service traefik                  # Deploy single service
uv run cstation docker apply <vps> --yes                              # Skip confirmation
uv run cstation docker apply <vps> --prune                            # Remove undeclared running containers

# Status and observability
uv run cstation docker status <vps>                                   # All services: declared vs running
uv run cstation docker status <vps> --service mailcow                  # Single service detail
uv run cstation docker logs <vps> --service traefik                    # Tail logs for a service
uv run cstation docker logs <vps> --service mailcow --lines 100

# Lifecycle
uv run cstation docker restart <vps> --service traefik                 # Restart a service
uv run cstation docker stop <vps> --service mailcow                    # Stop (don't remove)
uv run cstation docker remove <vps> --service mailcow                    # Remove containers + volumes
uv run cstation docker remove <vps> --service mailcow --purge          # Remove + delete data dirs

# Upgrade
uv run cstation docker upgrade <vps> --service traefik                 # Pull latest image + recreate
uv run cstation docker upgrade <vps>                                   # Upgrade all services
```

### Command Details

**`docker plan`** — Pre-flight + drift detection + port validation:

1. **Pre-flight**: SSH into the VPS, verify Docker daemon is running and `PW_NET` exists. If not, print: *"Docker infrastructure not ready. Run `cstation vps apply <vps>` first."* and exit.
2. **Port collision check**: Validate all declared `ports` across enabled fragments + already-running containers on the VPS. Fail at plan time with a clear error if two services both bind the same port.
3. **Drift detection**: For each enabled service, compare declared state vs actual:
   - Compose file content match?
   - Static config files match?
   - `.env` file match?
   - Container running with correct image tag?
   - Network membership correct?
4. **Orphan detection**: Running containers on the VPS not declared in any fragment file. Print a warning.

Prints a summary of what `apply` would change. Exits 0 if no drift, 1 if changes pending.

**`docker apply`** — Deploys each enabled service that has drift:
1. Pre-flight check (Docker + PW_NET).
2. Port collision check.
3. Create service directories on VPS (`/var/lib/<service>/`).
4. Write compose file + env file + static configs.
5. For `kind: Stack`: clone repo, write `.env` overrides, patch network.
6. Run `docker compose up -d`.
7. Verify containers are running.
8. Print summary of changes.

Interactive by default (shows changes, asks for confirmation). Use `--yes` to skip. Use `--prune` to also remove undeclared running containers.

**`docker status`** — Table output showing:
- Service name
- Kind (Container / Stack)
- Enabled? (from fragment)
- State: `running`, `stopped`, `missing`, `degraded`
- Image tag (running vs declared)
- Ports exposed
- Uptime

**`docker logs`** — Runs `docker compose logs` on the VPS. Supports `--lines` and `--follow`.

**`docker remove`** — Runs `docker compose down`. With `--purge`, also runs `docker compose down -v` and removes the service directory.

## Command Separation: vps apply vs docker apply

| Command | Scope | Reads | Does NOT do |
|---------|-------|-------|-------------|
| `cstation vps apply` | OS + Docker infrastructure (phases 1-13) | `vps.yaml` only | Deploy any containers |
| `cstation docker apply` | Deploy container services | `vps.yaml` (for SSH) + fragment files | Touch OS/Docker infrastructure |

Dependency chain: `cstation vps apply` must be run first (installs Docker, creates `PW_NET`, configures daemon). Then `cstation docker apply` deploys containers that use that infrastructure.

## Service Architecture

### ContainerService Protocol

```python
class ContainerService(Protocol):
    name: str
    kind: str                                        # "Container" or "Stack"

    def plan(self, ssh: SSHManager, config: dict) -> list[str]:
        """Compare declared vs actual state. Returns list of action descriptions."""

    def apply(self, ssh: SSHManager, config: dict) -> None:
        """Deploy/configure the service on the VPS."""

    def status(self, ssh: SSHManager) -> dict:
        """Return current state: {running, image, containers, ports, uptime}."""

    def stop(self, ssh: SSHManager, config: dict) -> None:
        """Stop the service without removing it."""

    def restart(self, ssh: SSHManager, config: dict) -> None:
        """Restart the service."""

    def remove(self, ssh: SSHManager, config: dict, purge: bool = False) -> None:
        """Remove the service. If purge=True, delete volumes and data dirs."""

    def upgrade(self, ssh: SSHManager, config: dict) -> None:
        """Pull latest image and recreate containers."""
```

### File Layout

```
src/cstation/commands/docker/
├── __init__.py
├── main.py                # docker_app Typer, registers sub-commands
├── apply.py               # docker plan / apply logic
├── status.py              # docker status
├── logs.py                # docker logs
├── lifecycle.py           # docker restart / stop / remove / upgrade
├── services/
│   ├── __init__.py        # imports all built-in services for auto-registration
│   ├── base.py            # ContainerService protocol + ImageService + StackService bases
│   ├── registry.py        # Service registry: name → class mapping
│   ├── image_service.py   # kind: Container base (generates compose from fragment)
│   ├── stack_service.py   # kind: Stack base (clones git repo + patches network)
│   ├── traefik.py         # Traefik-specific: static config generation
│   ├── portainer.py       # Portainer-specific: simple compose
│   ├── mailcow.py         # Mailcow-specific: clone, .env overrides, network patch
│   └── ...
└── compose/
    ├── __init__.py
    ├── render.py           # Compose file rendering (dict → YAML string)
    └── env_writer.py       # .env file writer
```

### Service Registry

```python
# src/cstation/commands/docker/services/registry.py

_SERVICE_CLASSES: dict[str, type[ContainerService]] = {}

def register_service(name: str, cls: type[ContainerService]) -> None:
    _SERVICE_CLASSES[name] = cls

def get_service(name: str) -> type[ContainerService]:
    if name not in _SERVICE_CLASSES:
        raise ValueError(f"Unknown service: {name}")
    return _SERVICE_CLASSES[name]

def available_services() -> list[str]:
    return sorted(_SERVICE_CLASSES.keys())
```

Built-in services self-register on import:

```python
# src/cstation/commands/docker/services/traefik.py
from .registry import register_service

class TraefikService(ImageService):
    name = "traefik"
    ...

register_service("traefik", TraefikService)
```

### Base Implementations

**`ImageService`** (`kind: Container` base) — handles the common pattern:
- Render compose file from `image`, `ports`, `volumes`, `env`, `network`, `restart_policy`.
- Write to `/var/lib/<service>/docker-compose.yml`.
- Write `.env` from `env` dict.
- Create service directories (`/var/lib/<service>/` and subdirs).
- Run `docker compose up -d`.
- Subclasses override to add static config generation (e.g., Traefik's `traefik.yml`).

**`StackService`** (`kind: Stack` base) — handles:
- Clone repo if `git_dir` doesn't exist.
- Write `.env` overrides from `env` dict.
- Patch compose file to add `PW_NET` as external network.
- Run `docker compose up -d` from `git_dir`.
- Subclasses override for service-specific patches (e.g., Mailcow's `mailcow.conf`).

### Implicit Service Ordering

Built-in services have implicit ordering in code. Traefik is always deployed first because all other services route through it. No `depends_on` field needed in fragment YAML for built-in services. Future: add `depends_on` support for custom/user-defined services.

## Idempotency

`docker plan` and `docker apply` must be idempotent — running them against an already-configured VPS should show "already configured" for every service.

Comparison checks:
1. **Compose file**: Compare the generated compose YAML with the file on the VPS (`cat` + string comparison or hash).
2. **Static configs**: Compare content of each generated config file with what's on the VPS.
3. **`.env` file**: Compare sorted key=value pairs.
4. **Container state**: `docker compose ps` — are all containers running with the correct image?
5. **Network**: Is the service container on `PW_NET`?

If all checks pass → print `[green]✓ already configured[/green]` and return.
If any check fails → print what differs and (for `apply`) converge.

## Apply Logic per Service Kind

### `kind: Container` (e.g., Traefik, Portainer)

```
1. ssh: mkdir -p /var/lib/<service>/{etc,conf,...}  (service-specific subdirs)
2. ssh: write /var/lib/<service>/docker-compose.yml
3. ssh: write /var/lib/<service>/.env
4. (subclass): ssh: write static config files (e.g., traefik.yml)
5. ssh: cd /var/lib/<service>/ && docker compose up -d
6. ssh: verify: docker compose ps (all containers running)
```

### `kind: Stack` (e.g., Mailcow)

```
1. ssh: test -d <git_dir> || git clone -b <branch> <git_repo> <git_dir>
2. (subclass): ssh: write service-specific config (mailcow.conf, etc.)
3. ssh: write <git_dir>/.env (env dict merged)
4. ssh: patch <git_dir>/docker-compose.yml — add PW_NET as external network to all services
5. ssh: cd <git_dir> && docker compose up -d
6. ssh: verify: docker compose ps (all containers running)
```

### Network Patching (for `kind: Stack`)

For stack services, the upstream compose file won't reference `PW_NET`. We patch it:

```python
def _patch_compose_network(ssh, compose_path, network):
    """Add external network to all services in docker-compose.yml."""
    # Read → parse YAML → add PW_NET to each service → write back
    # Only patch if not already present
```

This is done by reading the compose YAML, adding `networks: [PW_NET]` to each service definition, and adding `PW_NET` as an external network at the top level. The patch is idempotent.

## Traefik-Specific Design

Traefik is the first service to deploy (Phase C of the eu01 migration) and has unique requirements.

### Static Config

Written to `/var/lib/traefik/etc/traefik.yml` (mounted into container via volume). Includes HTTP→HTTPS redirect, forwarded headers, file logging, Cloudflare DNS challenge, and Prometheus metrics.

**Dashboard security**: `api.insecure` is NOT set — dashboard is only accessible via SSH tunnel (`ssh -L 8080:localhost:8080 root@<host>`, then `http://localhost:8080`).

```yaml
global:
  checknewversion: false
  sendanonymoususage: false
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
    forwardedHeaders:
      insecure: true
  websecure:
    address: ":443"
    forwardedHeaders:
      insecure: true
  smtp:
    address: ":25"
  submissions:
    address: ":465"
  submission:
    address: ":587"
  imaps:
    address: ":993"
  pop3s:
    address: ":995"
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: PW_NET
    watch: true
  file:
    directory: "/etc/traefik/conf"
    watch: true
certificatesResolvers:
  le_resolver:
    acme:
      email: "syner.catalyst@gmail.com"
      storage: "/letsencrypt/acme.json"
      caServer: "https://acme-v02.api.letsencrypt.org/directory"
      keyType: EC256
      tlsChallenge: {}
  le_dns_resolver:
    acme:
      email: "syner.catalyst@gmail.com"
      storage: "/letsencrypt/acme_dns.json"
      caServer: "https://acme-v02.api.letsencrypt.org/directory"
      keyType: EC256
      dnsChallenge:
        provider: cloudflare
        delayBeforeCheck: 15s
        resolvers:
          - "1.1.1.1:53"
          - "1.0.0.1:53"
api:
  dashboard: true
log:
  level: INFO
  filePath: "/etc/traefik/logs/traefik.log"
  format: json
accessLog:
  filePath: "/etc/traefik/logs/access.log"
  format: json
  bufferingSize: 100
metrics:
  prometheus:
    addEntryPointsLabels: true
    addServicesLabels: true
```

### Dynamic Config Directory

`/var/lib/traefik/conf/` — Traefik watches this directory for dynamic config files. Used for:
- Mailcow HTTP routes (admin UI + SOGo)
- Mailcow TCP routes (Postfix, Dovecot)
- Any other service that needs Traefik routing but doesn't use Docker labels

### Compose File (Generated on VPS)

Generated by `TraefikService` at `/var/lib/traefik/docker-compose.yml`. Note: no port `8080` is exposed — dashboard is accessed via SSH tunnel only.

```yaml
services:
  traefik:
    image: traefik:latest
    container_name: EU01_traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "25:25"
      - "465:465"
      - "587:587"
      - "993:993"
      - "995:995"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/lib/traefik/letsencrypt:/letsencrypt
      - /var/lib/traefik/conf:/etc/traefik/conf
      - /var/lib/traefik/etc/traefik.yml:/etc/traefik/traefik.yml:ro
      - /var/lib/traefik/logs:/etc/traefik/logs
    environment:
      DHPARAM_GENERATION: "false"
    env_file: .env
    command:
      - --configFile=/etc/traefik/traefik.yml
    networks:
      - PW_NET

networks:
  PW_NET:
    external: true
```

### Directory Structure on VPS

```
/var/lib/traefik/
├── docker-compose.yml
├── .env                        # secrets (CF_API_EMAIL, CF_API_KEY) — NOT committed
├── etc/
│   └── traefik.yml           # static config
├── conf/                      # dynamic config (Traefik watches this)
│   └── (dynamic route files go here)
├── letsencrypt/
│   └── acme.json             # ACME certificates (created by Traefik)
│   └── acme_dns.json         # DNS challenge certificates
└── logs/
    ├── traefik.log           # Traefik log (JSON format)
    └── access.log            # Access log (JSON format, buffered)
```

## Portainer-Specific Design

Portainer CE is deployed as a simple container with web UI.

### Compose File (Generated on VPS)

Generated by `PortainerService` at `/var/lib/portainer/docker-compose.yml`. Port 9000 is HTTP (direct access), port 9443 is HTTPS, port 8000 is the Edge tunnel for remote management of other VPSes.

```yaml
services:
  portainer:
    image: portainer/portainer-ce:latest
    container_name: EU01_portainer
    restart: always
    ports:
      - "9000:9000"
      - "9443:9443"
      - "8000:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/portainer/data:/data
    environment:
      PORTAINER_LOG_LEVEL: INFO
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    networks:
      - PW_NET

networks:
  PW_NET:
    external: true
```

### Directory Structure on VPS

```
/var/lib/portainer/
├── docker-compose.yml
├── .env
└── data/                      # Portainer data (created by Portainer)
```

## Mailcow-Specific Design

Mailcow ships its own `docker-compose.yml` with ~12 containers. The `MailcowService` handles:

### Clone + Configure

```
1. Clone: git clone -b master https://github.com/mailcow/mailcow-dockerized /opt/mailcow
2. Generate config: cd /opt/mailcow && ./generate_config.sh
3. Write mailcow.conf overrides:
   - SKIP_LETS_ENCRYPT=y
   - SKIP_NGINX=y
   - HTTP_PORT=8082
   - HTTPS_PORT=8443
   - MAILCOW_HOSTNAME=mail.synercatalyst.com
4. Patch docker-compose.yml: add PW_NET to all services
5. docker compose up -d
```

### Traefik Dynamic Config for Mailcow

After Mailcow is deployed, the `TraefikService` writes dynamic route files:

**HTTP routes** (`/var/lib/traefik/conf/mailcow-http.yml`):
```yaml
http:
  routers:
    mailcow-admin:
      entryPoints: ["websecure"]
      rule: "Host(`mail.synercatalyst.com`)"
      service: mailcow-internal
      tls:
        certResolver: le_resolver
  services:
    mailcow-internal:
      loadBalancer:
        servers:
          - url: "http://mailcow-nginx:8082"
```

**TCP routes** (`/var/lib/traefik/conf/mailcow-tcp.yml`):
```yaml
tcp:
  routers:
    smtp:
      entryPoints: ["smtp"]
      service: mailcow-postfix
      rule: "HostSNI(`*`)"
    submissions:
      entryPoints: ["submissions"]
      service: mailcow-postfix-ssl
      rule: "HostSNI(`*`)"
    imaps:
      entryPoints: ["imaps"]
      service: mailcow-dovecot
      rule: "HostSNI(`*`)"
  services:
    mailcow-postfix:
      loadBalancer:
        servers:
          - address: "postfix-mailcow:25"
    mailcow-postfix-ssl:
      loadBalancer:
        servers:
          - address: "postfix-mailcow:465"
    mailcow-dovecot:
      loadBalancer:
        servers:
          - address: "dovecot-mailcow:993"
```

## Secrets

Two types of environment variables:

1. **Non-secret config** → declared in fragment YAML `env` section (committed to git). Written as compose `environment` (inline).
2. **Secrets** → declared in fragment YAML `secrets` section as key names only (e.g., `secrets: [CF_API_EMAIL, CF_API_KEY]`). Written to a `.env` file on the VPS only (NOT committed). The fragment also sets `env_file: .env` so compose loads the secrets at runtime.

**How it works:**
- Fragment `env` → compose `environment` (non-secret, committed, visible in compose file).
- Fragment `secrets` + `env_file` → `.env` file on VPS only (secret values, NOT committed).
- On first `docker apply`: cstation writes a template `.env` with placeholder values (`REPLACE_ME`). User must SSH in and edit with real values.
- On subsequent applies: cstation does NOT overwrite existing `.env` files (preserves user-set secrets).
- `docker plan` warns if secrets in `.env` still contain placeholder values.

Example Traefik fragment:
```yaml
env_file: .env
env:
  DHPARAM_GENERATION: "false"    # non-secret → compose environment
secrets:
  - CF_API_EMAIL                  # secret → .env on VPS only
  - CF_API_KEY                    # secret → .env on VPS only
```

Secrets are never printed in plan output or committed to git. Future: add `cstation docker env` command to manage secrets interactively.

## Migration: Retire Ansible Playbook System

### Current State

- `src/cstation/commands/docker/main.py` — registers `playbook_app` sub-app
- `src/cstation/commands/docker/playbook.py` — `list` and `push` commands that shell out to `ansible-playbook`
- `src/cstation/main.py` — imports and registers `docker_app`

### Migration Steps

1. Remove `src/cstation/commands/docker/playbook.py`.
2. Replace `src/cstation/commands/docker/main.py` with new docker command group.
3. Add new modules: `apply.py`, `status.py`, `logs.py`, `lifecycle.py`, `services/`, `compose/`.
4. Update `src/cstation/main.py` registration (no change needed — same `docker_app` name).
5. Remove any Ansible-specific inventory/config dependencies.

### Backward Compatibility

- `cstation docker playbook list` and `cstation docker playbook push` will be removed.
- No migration path — users should switch to the declarative `docker plan/apply` workflow.
- Fragment files replace the Ansible playbook + vars file pattern.

## Migration: VPS Config Structure

### Current State

- `config/vps/eu01.synercatalyst.com.yaml` — single flat file
- `config/vps/sg07.ansis.com.sg.yaml` — single flat file

### Migration Steps

1. Create directory: `config/vps/eu01.synercatalyst.com/`
2. Move `eu01.synercatalyst.com.yaml` → `config/vps/eu01.synercatalyst.com/vps.yaml`
3. Create fragment files: `traefik.yaml`, `portainer.yaml`, `mailcow.yaml`
4. Delete old flat file: `config/vps/eu01.synercatalyst.com.yaml`
5. Repeat for sg07 when ready
6. Update `vps init` to write to `config/vps/<name>/vps.yaml` instead of `config/vps/<name>.yaml`
7. Update all VPS commands to accept directory path or VPS name

## Implementation Roadmap

### Phase 1: Core + Config Migration + Traefik + Portainer

Delivers: `cstation docker plan/apply/status` working end-to-end for Traefik + Portainer on eu01.

- [ ] Migrate eu01 config: `config/vps/eu01.synercatalyst.com.yaml` → `config/vps/eu01.synercatalyst.com/vps.yaml`
- [ ] Create fragment files: `traefik.yaml`, `portainer.yaml`, `mailcow.yaml`
- [ ] Update `vps init` to write `config/vps/<name>/vps.yaml`
- [ ] Update all VPS commands to accept directory path or VPS name
- [ ] Create `ContainerService` protocol in `services/base.py`
- [ ] Create `ImageService` base class (`kind: Container`) in `services/image_service.py`
- [ ] Create service registry in `services/registry.py`
- [ ] Create compose file renderer in `compose/render.py`
- [ ] Create `.env` writer in `compose/env_writer.py`
- [ ] Implement `TraefikService` in `services/traefik.py`
- [ ] Implement `PortainerService` in `services/portainer.py`
- [ ] Implement `docker plan` and `docker apply` commands
- [ ] Implement `docker status` command
- [ ] Add pre-flight check (Docker daemon + PW_NET)
- [ ] Add port collision detection
- [ ] Add orphan detection
- [ ] Retire `playbook.py`, update `main.py`
- [ ] Tests: plan/apply for traefik + portainer (mocked SSH)
- [ ] Verify on eu01: Traefik running, API at `http://localhost:8080`; Portainer at `https://localhost:9443`

### Phase 2: Mailcow Deploy

Delivers: `kind: Stack` support + Mailcow deployment.

- [ ] Create `StackService` base class (`kind: Stack`) in `services/stack_service.py`
- [ ] Implement `MailcowService` in `services/mailcow.py`
- [ ] Implement network patching for stack services
- [ ] Enable `mailcow.yaml` fragment (`enabled: true`)
- [ ] Write Traefik dynamic config for Mailcow (HTTP + TCP routes)
- [ ] Test: deploy Mailcow on eu01 routed through Traefik

### Phase 3: Other Services

Delivers: PostgreSQL, n8n templates.

- [ ] Implement `PostgresService` (`kind: Container`, with init scripts)
- [ ] Implement `N8nService` (`kind: Container`, with volume mounts)
- [ ] Test each service independently

### Phase 4: Lifecycle Management

Delivers: `logs`, `restart`, `stop`, `remove`, `upgrade` commands.

- [ ] Implement `docker logs` command
- [ ] Implement `docker restart` command
- [ ] Implement `docker stop` command
- [ ] Implement `docker remove` command (with `--purge`)
- [ ] Implement `docker upgrade` command (pull + recreate)

### Phase 5: Generic Service + Extensibility

Delivers: Custom/arbitrary services without a built-in template.

- [ ] Add "custom" service type — user provides their own compose content in fragment
- [ ] Validate compose content before writing
- [ ] Allow `compose_content` field in fragment for raw compose YAML
- [ ] Add `depends_on` support for custom services
- [ ] Documentation for adding new service types

## Open Questions

1. ~~**ACME email**: Should the `le_resolver` email be in the fragment YAML or a separate secrets file?~~ **Resolved**: Fragment YAML — email is not secret.
2. ~~**Traefik dashboard security**: The spec uses `api.insecure: true` for MVP.~~ **Resolved**: `api.insecure` removed. Dashboard accessible via SSH tunnel only (`ssh -L 8080:localhost:8080`).
3. **Mailcow network patching**: Should we patch the upstream `docker-compose.yml` directly, or layer a `docker-compose.override.yml`? Override is safer and survives `git pull` upgrades.
4. **Container health checks**: Should `docker status` check container health (`docker inspect --format='{{.State.Health.Status}}'`) or just running state?
5. **Rollback**: If `apply` fails mid-deploy (e.g., Mailcow compose fails), should we attempt to roll back to the previous state?
6. **Secrets management**: Should we add a `cstation docker env` command for interactive secrets management, or is manual `.env` editing sufficient for MVP?