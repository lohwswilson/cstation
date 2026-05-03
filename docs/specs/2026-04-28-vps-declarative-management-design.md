# VPS Declarative Management (Design)

## Summary

CStation manages VPS infrastructure (OS, Docker runtime) via `cstation vps init/plan/apply`, and Docker container services via `cstation docker plan/apply`. These are two separate commands with clear separation: `vps apply` handles OS + Docker infrastructure only; `docker apply` handles container deployment.

Each VPS has its own config directory containing a main `vps.yaml` file and optional container fragment files:

```
config/vps/<vps-name>/
├── vps.yaml              ← kind: VPS (identity, access, facts, os, docker)
├── traefik.yaml          ← kind: Container
├── portainer.yaml        ← kind: Container
└── mailcow.yaml          ← kind: Stack
```

This design replaces legacy Ansible/PW_CS usage with a stable schema, deterministic naming, validation, and an ordered apply pipeline. The workflow starts with `vps init` to capture VPS facts, then `vps apply` for infrastructure, then `docker apply` for containers.

## Goals

- One VPS = one config directory, applied independently.
- A read-only `vps init` produces `vps.yaml` from provider metadata + SSH facts (no server changes).
- Provider-agnostic interface (Hetzner first) for compute + networking + storage.
- Two-phase apply: OS/Docker infrastructure (`vps apply`), then containers (`docker apply`).
- Container declarations in separate fragment files — one file per service, clean git diffs.
- All services on `PW_NET` for Traefik routing.
- Built-in service templates for common stacks (Traefik, Mailcow, Portainer).
- Low cognitive load: shallow CLI (generally 2 levels deep).

## Non-Goals (MVP)

- Automated DB creation/migrations and automated Odoo backup/restore.
- Full Terraform-style state management and drift correction across all layers.
- Multi-VPS apply in a single command.
- Kubernetes/Swarm orchestration (Compose-first; future extensibility).
- Container image building (pull from registry only in MVP).
- Secret rotation or vault integration (`.env` files on the VPS for now).

## Terminology

- **VPS**: One machine. One config directory. Applied independently.
- **Fragment**: A YAML file in the VPS config directory (e.g., `traefik.yaml`) declaring a container or stack.
- **Container** (`kind: Container`): A service where cstation generates the compose file from the fragment config.
- **Stack** (`kind: Stack`): A service where cstation clones a git repo and patches it (e.g., Mailcow).
- **Component**: Reusable base definition for services/apps plus per-VPS overrides.
- **Artifact**: A buildable/syncable input referenced by a VPS (git sources, Docker images).

## Repository Layout

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

The main `vps.yaml` file is the only required file. Fragment files are added when containers need to be deployed. Fragment discovery: all `*.yaml` files in the directory except `vps.yaml`.

## VPS Schema (High Level)

### `vps.yaml` — Main VPS File

Contains everything `cstation vps apply` needs. Does NOT contain container declarations.

```yaml
apiVersion: cstation/v1
kind: VPS
identity: { name, stage, region }
access: { host, user, port }
facts: { os, cpu, memory, disks, network, hostname, packages }
os:
  hostname: eu01.synercatalyst.com
  baseline: { upgrade_all, packages, shell, terminal, swap, tuning, sshd, fail2ban, firewall }
  journald: { system_max_use, forward_to_syslog }
docker:
  daemon: { log_driver, log_opts, storage_driver, live_restore, iptables }
  networks: [PW_NET]
  directories: [/var/lib/perfectwork]
```

### Fragment Files — Container/Stack Declarations

Each fragment is a separate YAML file in the VPS config directory. See `docs/superpowers/specs/2026-04-29-docker-service-management-design.md` for full schema.

```yaml
# kind: Container (cstation generates compose file)
apiVersion: cstation/v1
kind: Container
name: traefik
enabled: true
image: traefik:latest
container_name: EU01_traefik
network: PW_NET
ports: [...]
volumes: [...]
env: {...}          # non-secret config → compose environment
env_file: .env      # secrets loaded from .env file on VPS
secrets: [...]      # secret key names → .env on VPS only (NOT committed)
restart_policy: unless-stopped
static_config: {...}  # optional, service-specific
```

```yaml
# kind: Stack (cstation clones git repo and patches)
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

## Command Separation

| Command | Scope | Reads | Does NOT do |
|---------|-------|-------|-------------|
| `cstation vps apply` | OS + Docker infrastructure (phases 1-13) | `vps.yaml` only | Deploy any containers |
| `cstation docker apply` | Deploy container services | `vps.yaml` (for SSH) + fragment files | Touch OS/Docker infrastructure |

Dependency: `vps apply` must run first (installs Docker, creates `PW_NET`, configures daemon). Then `docker apply` deploys containers.

## Naming and Addressing

- Container and compose project names are auto-generated deterministically from VPS and service/app identity.
  - Example: Postgres container `SG07_DB_PG18` and network alias `pg18`.
- Applications connect to Postgres via **network alias** (`pg18`, `pg16`) rather than container names.
- Validation fails at plan-time on name collisions.

## Secrets

Primary recommendation:

- Use `.env` files on the VPS (not committed to git) for app secrets (DB passwords, admin password, SMTP).
- Non-secret config goes in fragment YAML files (committed to git).
- Provider tokens can be environment variables or keychain; MVP uses environment variables.

Secrets are never printed in logs and are excluded from rendered diffs by default.

## Artifacts (Git and Docker Images)

Artifacts are generic and can represent:

- **Git artifact**: multiple git sources tracked by moving branches (refs are quoted strings like `"18.0"`), optional fork sync mode for PR workflows, optional sparse includes for OCA modules.
- **Docker image artifact**: build context + Dockerfile + tags + optional registry push.

Artifacts are version-controlled in the repo for consistency across SG/US/DE.

## Apply Pipeline (Sequence)

### `cstation vps apply <vps>` — OS + Docker Infrastructure

Phases 1-13 run in order. NO container deployment.

1. Cloud: ensure VPS exists and requested cloud network/firewall/storage resources exist
2. SSH: verify access and bootstrap non-root sudo user if configured
3. OS: baseline packages, sshd hardening, OS firewall
4. Docker: install/enable Docker engine, configure daemon, create networks, create directories

Current implemented phases (13 total):

1. `upgrade_all` — upgrade all installed packages
2. `packages` — install missing packages
3. `shell` — set default shell
4. `terminal` — set TERM in /etc/environment
5. `sshd` — configure SSH daemon
6. `firewall` — configure UFW
7. `swap` — create swap file, set swappiness, add to fstab
8. `tuning` — write sysctl params + journald config
9. `fail2ban` — write jail.local, restart
10. `hostname` — set hostname via hostnamectl
11. `docker_daemon` — write /etc/docker/daemon.json, restart docker
12. `docker_networks` — create Docker networks
13. `docker_directories` — create directories

After `vps apply` completes, Docker is running, `PW_NET` exists, and infrastructure directories are created. Then run `docker apply` to deploy containers.

### `cstation docker apply <vps>` — Container Deployment

See `docs/superpowers/specs/2026-04-29-docker-service-management-design.md` for full details.

1. Pre-flight: verify Docker running + `PW_NET` exists
2. Port collision check across all enabled fragments
3. Orphan detection: running containers not in any fragment
4. For each enabled fragment (ordered: Traefik first):
   - `kind: Container`: generate compose file, write configs, `docker compose up -d`
   - `kind: Stack`: clone repo, write overrides, patch network, `docker compose up -d`
5. Verify all containers running

Apply is interactive by default and requires an explicit `--prune/--allow-delete` to delete resources.

## Command UX (MVP)

Top level:

- `cstation vps ...` (primary — OS + Docker infrastructure)
- `cstation docker ...` (container deployment)
- `cstation artifact ...` (build/update artifacts referenced by vps)
- `cstation github ...` (advanced/legacy low-level repo tooling; optional)

CLI arguments accept both directory paths and VPS names:

```bash
# By directory path (explicit)
cstation vps apply config/vps/eu01.synercatalyst.com
cstation docker apply config/vps/eu01.synercatalyst.com

# By VPS name (auto-discover in config/vps/)
cstation vps apply eu01.synercatalyst.com
cstation docker apply eu01.synercatalyst.com
```

### VPS Commands

- `cstation vps init <provider>/<account>:<id> [--out config/vps/<name>] [--force] [--user root] [--port 22] [--key <ssh_key>]`
- `cstation vps plan <vps>`
- `cstation vps apply <vps>` (interactive)
- `cstation vps status <vps-or-id> --provider <provider>`
- `cstation vps ls --provider <provider>`
- `cstation vps doctor <vps>` (future)
- `cstation vps sync-code <vps>` (future, push-only rsync)

### Docker Commands

- `cstation docker plan <vps>` (dry-run container changes)
- `cstation docker plan <vps> --service traefik` (single service)
- `cstation docker apply <vps>` (deploy all enabled services)
- `cstation docker apply <vps> --service traefik` (single service)
- `cstation docker apply <vps> --yes` (skip confirmation)
- `cstation docker apply <vps> --prune` (remove undeclared containers)
- `cstation docker status <vps>` (show container state)
- `cstation docker logs <vps> --service <name>` (future)
- `cstation docker restart/stop/remove/upgrade <vps> --service <name>` (future)

### Artifact Commands (future)

- `cstation artifact update <artifact-id>`
- `cstation artifact build <artifact-id>`

## Port Management Recommendation

Default recommendation is to avoid host port publishing for Odoo services and route via Traefik on the docker network. If host ports are required (debug), require explicit port declaration and validate collisions.

`cstation docker plan` validates all declared `ports` across enabled fragments + running containers. Fail at plan time if two services both bind the same port.

## VPS Init (Read-Only Facts)

`cstation vps init` is a read-only command that resolves provider metadata, connects via SSH, and writes a per-VPS `vps.yaml` file. It does not change the server.

Behavior:
- Target is provider-based: `<provider>/<account>:<id>`
- `stage` is user-provided, defaulting to `prod`
- `name` and `region` are inferred from provider metadata
- Output path defaults to `config/vps/<name>/vps.yaml` (creates directory)
- Refuses to overwrite existing files unless `--force`

CLI examples:
- `cstation vps init hetzner/ANSIS:123456` → creates `config/vps/eu01.synercatalyst.com/vps.yaml`
- `cstation vps init vultr/MAIN:9b2f... --stage prod`
- `cstation vps init hetzner/ANSIS:123456 --out config/vps/sg07.ansis.com.sg`

OS facts captured (key set only):
- OS release + kernel
- CPU model + vCPU count
- RAM total (MB)
- Disk summary
- Network interfaces + primary IP
- Key packages installed (curated list: openssh-server, ufw/nftables, fail2ban, docker, python3, rsync, curl, git, sudo)

The `vps.yaml` output includes:
- `identity`: name, stage, region
- `access`: host, user, port, key
- `facts`: OS/CPU/RAM/disk/network + key packages
- `os.baseline`: placeholder for packages/sshd/firewall config

Fragment files (e.g., `traefik.yaml`) are created manually by the user, not by `vps init`.

## Docker Service Management

See `docs/superpowers/specs/2026-04-29-docker-service-management-design.md` for the full design of the `cstation docker` command group, including:

- Fragment schema (`kind: Container` and `kind: Stack`)
- Service architecture (ContainerService protocol, registry, base implementations)
- Apply logic per service kind
- Traefik-specific design (static config, dynamic config, compose generation)
- Portainer-specific design
- Mailcow-specific design (clone + configure, network patching)
- Idempotency
- Pre-flight checks, port collision detection, orphan detection
- Implementation roadmap

Key points:
- `cstation vps apply` handles OS + Docker infrastructure only (no containers).
- `cstation docker apply` handles container deployment only (no OS/Docker infrastructure).
- Container declarations live in fragment files (`traefik.yaml`, `portainer.yaml`, etc.), NOT in `vps.yaml`.
- Infrastructure services (Traefik, Portainer) store data at `/var/lib/<service>/`. Odoo uses `/var/lib/perfectwork/`.
- The old Ansible-based `cstation docker playbook` commands have been retired.

## PostgreSQL Docker Container

CStation deploys PostgreSQL as a declarative `kind: Container` fragment. The fragment is tuned per-VPS based on the server's hardware profile (CPU, RAM, disk type) and accessed over an SSH tunnel for security.

### Fragment Schema

```yaml
apiVersion: cstation/v1
kind: Container
name: US02_DB
enabled: true
image: postgres:18
container_name: US02_DB
network: PW_NET
ports:
  - "127.0.0.1:1488:5432"     # localhost-only binding (SSH tunnel required)
volumes:
  - "/var/lib/postgresql:/var/lib/postgresql/data"
secrets:
  - POSTGRES_PASSWORD            # resolved from ~/.config/cstation/config.yaml → .env on VPS
env:
  POSTGRES_USER: postgres
  PGDATA: /var/lib/postgresql/data/pgdata
restart_policy: always
command:
  - "postgres"
  - "-c"
  - "max_connections=120"
  # ... (see Tuning section below)
```

Key design decisions:

| Decision | Detail |
|----------|--------|
| **Port binding** | `127.0.0.1:1488:5432` — localhost only. Never expose PostgreSQL on a public interface. Remote access requires SSH tunnel. |
| **Port convention** | `1488` is the standard offset port for PostgreSQL across all VPS (SG01, US02, etc.). Consistent port reduces cognitive load. |
| **Secrets in `.env`** | `POSTGRES_PASSWORD` is declared under `secrets`, resolved from `~/.config/cstation/config.yaml`, and written to `.env` on the VPS. It is never committed to the repo or printed in logs. |
| **PGDATA subdirectory** | `PGDATA` is set to `/var/lib/postgresql/data/pgdata` (a subdirectory of the volume mount) to avoid PostgreSQL initdb failures when the volume mountpoint has lost+found or other files. |
| **Volume path** | `/var/lib/postgresql` on the host — distinct from `/var/lib/perfectwork/` which is for application data. |
| **`command` overrides** | PostgreSQL tuning is done via `-c` flags in the `command` array, not via a mounted `postgresql.auto.conf`. This keeps tuning declarative in the fragment and avoids config drift between the fragment and a file on disk. |

### PostgreSQL Tuning Guidelines

Tuning parameters are derived from the server's hardware profile. The following table shows the two current reference profiles:

| Parameter | US02 (ARM, 8 GB RAM) | SG01 (x86, 48 GB RAM) | Notes |
|-----------|----------------------|-----------------------|-------|
| `shared_buffers` | 1 GB | 4 GB | 25% of dedicated PG RAM (US02: 4 GB → 1 GB) |
| `effective_cache_size` | 3 GB | 12 GB | 75% of dedicated PG RAM |
| `work_mem` | 16 MB | 32 MB | Per-sort-operation memory |
| `maintenance_work_mem` | 256 MB | 512 MB | For VACUUM, CREATE INDEX |
| `max_connections` | 120 | 200 | Based on expected concurrency |
| `min_wal_size` | 1 GB | 1 GB | |
| `max_wal_size` | 4 GB | 4 GB | |
| `wal_buffers` | 32 MB | 64 MB | |
| `checkpoint_completion_target` | 0.9 | 0.9 | |
| `random_page_cost` | 1.1 | 1.1 | SSD assumption |
| `effective_io_concurrency` | 200 | 200 | SSD assumption |
| `wal_compression` | on | on | pglz in PG18 |
| `max_worker_processes` | 4 | 8 | Match vCPU or fewer |
| `max_parallel_workers_per_gather` | 2 | 4 | |
| `max_parallel_workers` | 4 | 8 | |
| `max_parallel_maintenance_workers` | 2 | 2 | |
| `idle_in_transaction_session_timeout` | 300000 (5 min) | 300000 (5 min) | Prevents idle transactions from holding locks |
| `shared_preload_libraries` | pg_stat_statements | pg_stat_statements | |

**Tuning formula** (for new VPS):

1. Determine dedicated PG RAM = `total_ram * 0.5` (for mixed app+DB servers) or `total_ram * 0.75` (for DB-only).
2. `shared_buffers` = dedicated PG RAM / 4.
3. `effective_cache_size` = dedicated PG RAM * 0.75.
4. `work_mem` = 16 MB for ≤8 GB RAM, 32 MB for ≤32 GB, 64 MB for 64 GB+.
5. `max_worker_processes` = min(vCPU, 8).
6. All other params remain constant across profiles.

### `io_method` on PostgreSQL 18

PostgreSQL 18 introduced `io_method` with valid values `sync`, `worker`, and `io_uring`. **Do not set `io_method`** in the fragment command:

- `aio` is not a valid value (was removed/renamed in PG18).
- `io_uring` requires kernel support and specific permissions — it fails on Netcup ARM VPS with "Operation not permitted".
- Omitting `io_method` entirely lets PG18 default to `sync`, which is safe on all platforms.

If `io_uring` is desired, validate kernel support first: `grep io_uring /proc/kallsyms && echo OK || echo MISSING`.

### Remote Access via SSH Tunnel

PostgreSQL is only accessible via SSH tunnel. The connection flow:

```
Client (DBeaver, pgAdmin, psql)
  ↓ SSH tunnel (port 22 → VPS)
  → 127.0.0.1:1488 (localhost on VPS)
  → PostgreSQL container port 5432
```

**DBeaver setup:**

1. **Main tab**: Host `127.0.0.1`, Port `1488`, Database `postgres`, User `postgres`.
2. **SSH tab**: Enable "Use SSH Tunnel", Host `<vps-hostname>`, Port `22`, User `root`, Auth type: Public Key → your SSH key.

**psql via SSH tunnel:**

```bash
# Manual tunnel
ssh -L 1488:127.0.0.1:1488 root@us02.synercatalyst.com -N -f
psql -h 127.0.0.1 -p 1488 -U postgres

# Or one-liner
ssh root@us02.synercatalyst.com "docker exec US02_DB psql -U postgres"
```

### Secrets Management

PostgreSQL secrets are stored outside the fragment YAML to prevent credential leakage:

```yaml
# ~/.config/cstation/config.yaml
vps:
  secrets:
    us02.synercatalyst.com:
      US02_DB:
        POSTGRES_PASSWORD: "<secret-value>"
```

At deploy time, `ImageService._render_env()` merges `env` + resolved secrets into a single `.env` file on the VPS, and `_render_compose()` adds `env_file: .env` to the compose service. The PostgreSQL Docker entrypoint reads `POSTGRES_PASSWORD` from the environment.

### SG01 Legacy Note

The SG01 database fragment (`config/vps/sg01.synercatalyst.com/SG01_DB.yaml`) still has `POSTGRES_PASSWORD` in plaintext under `env`. This should be migrated to secrets for consistency.

### Deployment Checklist

1. Ensure `vps apply <hostname>` has been run (Docker + PW_NET ready).
2. Create fragment YAML in `config/vps/<hostname>/` with tuning params for the server profile.
3. Add `POSTGRES_PASSWORD` to `~/.config/cstation/config.yaml` under `vps.secrets.<hostname>.<service_name>`.
4. Run `cstation docker apply <hostname> --yes`.
5. Verify: `ssh root@<hostname> "docker exec <container_name> psql -U postgres -c 'SHOW shared_buffers'"`.
6. Connect from Mac via SSH tunnel (DBeaver or psql).

## MVP Slice

Start with one Hetzner VPS:

1. `cstation vps init hetzner/ANSIS:123456` → creates `config/vps/eu01.synercatalyst.com/vps.yaml`
2. Edit `vps.yaml` — add baseline config, swap, tuning, fail2ban, Docker, hostname
3. `cstation vps apply eu01.synercatalyst.com` — OS + Docker infrastructure
4. Create `config/vps/eu01.synercatalyst.com/traefik.yaml` — Traefik fragment
5. `cstation docker apply eu01.synercatalyst.com --service traefik` — deploy Traefik
6. Create `config/vps/eu01.synercatalyst.com/portainer.yaml` — Portainer fragment
7. `cstation docker apply eu01.synercatalyst.com --service portainer` — deploy Portainer
8. (Future) Create `mailcow.yaml` → `cstation docker apply --service mailcow`

## First Implementation Milestone (Hetzner Create Only)

The first executable milestone is a Hetzner-only VPS creation flow:

- `cstation vps create --provider hetzner --name <name> --region <region> --type <type> --image <image> --ssh-key <key>`
- `cstation vps ls --provider hetzner`
- `cstation vps status <name-or-id> --provider hetzner`
- `cstation vps delete <name-or-id> --provider hetzner` (requires confirmation)