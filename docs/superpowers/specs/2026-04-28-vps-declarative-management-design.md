# VPS Declarative Management (Design)

## Summary

CStation will manage a single VPS end-to-end from one declarative YAML entry file: cloud resources (provider), OS baseline, Docker runtime, shared services (Traefik/Postgres/Portainer), applications (multiple Odoo instances and other stacks), and push-only code sync to the VPS. The primary user workflow is `cstation vps init/plan/apply/doctor/status <vps.yml>` with interactive apply by default.

This design replaces legacy Ansible/PW_CS usage by introducing a stable schema, deterministic naming, validation (ports, collisions, missing secrets), and an ordered apply pipeline. The workflow starts with `vps init` to capture VPS facts into a per-VPS config file.

## Goals

- One VPS = one declarative config entry file, applied one VPS at a time.
- A read-only `vps init` produces the per-VPS YAML from provider metadata + SSH facts (no server changes).
- Provider-agnostic interface (Hetzner first) for compute + networking + storage.
- End-to-end apply pipeline: cloud → SSH access → OS baseline → Docker → services → apps → (optional) sync.
- Multiple Odoo instances per VPS, potentially running different Odoo major versions on the same VPS.
- Support multiple Postgres containers per VPS (different versions) and connect apps via Docker network aliases.
- Push-only rsync-based sync to `/var/lib/perfectwork`, non-atomic, no automatic restarts after sync.
- Low cognitive load: shallow CLI (generally 2 levels deep).

## Non-Goals (MVP)

- Automated DB creation/migrations and automated Odoo backup/restore.
- Full Terraform-style state management and drift correction across all layers.
- Multi-VPS apply in a single command.
- Kubernetes/Swarm orchestration (Compose-first; future extensibility).

## Terminology

- **VPS**: One machine. One config entry file. Applied independently.
- **Component**: Reusable base definition for services/apps (Traefik/Postgres defaults) plus per-VPS overrides.
- **Artifact**: A buildable/syncable input referenced by a VPS (e.g., git sources for Odoo/OCA, custom Docker images). This is not Odoo-specific.
- **Bundle** (alias term): An artifact representing a versioned set of git sources (e.g., Odoo 18.0 + OCA repos). Internally we treat this as one artifact type.

## Repository Layout

- `config/vps/<stage>_<region>_<vps_name>.yaml` (entry point; one file per VPS, flat for easy sorting)
- `artifacts/*.yml` (git-based artifacts, docker-image artifacts)
- `common/components/*.yml` (shared component defaults, referenced by vps configs)

The entry file is the only required file in MVP. Future extensions can add explicit includes for safety and predictability.

## VPS Schema (High Level)

Each VPS config includes:

- **Identity**: `name`, `stage`, `region`, `tags`
- **Cloud**: provider + optional server id + labels/tags (name/tags primary; id supported)
- **Access**: SSH host/user/port/key reference
- **OS**: baseline packages, sshd policy, firewall policy (UFW/nftables), creation of non-root sudo user
- **Docker**:
  - create/ensure Docker installed
  - create/ensure shared docker networks (e.g., `PW_NET`)
  - optional volumes/directories under `/var/lib/perfectwork`
- **Services**:
  - Traefik (docker provider + file provider)
  - Postgres services (multiple allowed)
  - Portainer (optional)
- **Apps**:
  - Odoo apps (multiple, each with version, domains, DB target alias, and `odoo.settings` 1:1 config keys)
  - Other apps (email server stacks, Hermes agent, etc.)
- **Sync**:
  - rsync push-only rules for directories, including large code trees
  - explicitly non-atomic by default
  - no automatic restart after sync

## Naming and Addressing

- Container and compose project names are auto-generated deterministically from VPS and service/app identity.
  - Example: Postgres container `SG07_DB_PG18` and network alias `pg18`.
- Applications connect to Postgres via **network alias** (`pg18`, `pg16`) rather than container names.
- Validation fails at plan-time on name collisions.

## Secrets

Primary recommendation:

- Use `.env` files (not committed) for app secrets (DB passwords, admin password, SMTP).
- Provider tokens can be environment variables or keychain; MVP may start with environment variables.

Secrets are never printed in logs and are excluded from rendered diffs by default.

## Artifacts (Git and Docker Images)

Artifacts are generic and can represent:

- **Git artifact**: multiple git sources tracked by moving branches (refs are quoted strings like `"18.0"`), optional fork sync mode for PR workflows, optional sparse includes for OCA modules.
- **Docker image artifact**: build context + Dockerfile + tags + optional registry push.

Artifacts are version-controlled in the repo for consistency across SG/US/DE. The tool records a resolved receipt per operation with commit SHAs.

## Apply Pipeline (Sequence)

For `cstation vps apply <vps.yml>`:

1. Cloud: ensure VPS exists and requested cloud network/firewall/storage resources exist
2. SSH: verify access and bootstrap non-root sudo user if configured
3. OS: baseline packages, sshd hardening, OS firewall
4. Docker: install/enable Docker engine, create networks
5. Services: deploy Traefik/Postgres/Portainer
6. Apps: deploy Compose projects for each app (Odoo instances, etc.)
7. Sync: optional step or separate command; does not restart apps by default

Apply is interactive by default and requires an explicit `--prune/--allow-delete` to delete resources.

## Command UX (MVP)

Top level:

- `cstation vps ...` (primary)
- `cstation artifact ...` (build/update artifacts referenced by vps)
- `cstation github ...` (advanced/legacy low-level repo tooling; optional)

MVP commands:

- `cstation vps init <provider>/<account>:<id> [--stage prod] [--out config/vps/<stage>_<region>_<vps_name>.yaml] [--force] [--user root] [--port 22] [--key <ssh_key>]`
- `cstation vps plan <vps.yml>`
- `cstation vps apply <vps.yml>` (interactive)
- `cstation vps doctor <vps.yml>`
- `cstation vps status <vps.yml>`
- `cstation vps sync-code <vps.yml>` (push-only rsync to `/var/lib/perfectwork`, no restarts)
- `cstation artifact update <artifact-id>`
- `cstation artifact build <artifact-id>`

## Port Management Recommendation

Default recommendation is to avoid host port publishing for Odoo services and route via Traefik on the docker network. If host ports are required (debug), require explicit port declaration and validate collisions.

## VPS Init (Read-Only Facts)

`cstation vps init` is a read-only command that resolves provider metadata, connects via SSH, and writes a per-VPS YAML entry file. It does not change the server.

Behavior:
- Target is provider-based: `<provider>/<account>:<id>`
- `stage` is user-provided, defaulting to `prod`
- `name` and `region` are inferred from provider metadata
- Output path defaults to `config/vps/<stage>_<region>_<name>.yaml`
- Refuses to overwrite existing files unless `--force`

CLI examples:
- `cstation vps init hetzner/ANSIS:123456`
- `cstation vps init vultr/MAIN:9b2f... --stage prod`
- `cstation vps init hetzner/ANSIS:123456 --out config/vps/prod_hel1_sg05.yaml`

OS facts captured (key set only):
- OS release + kernel
- CPU model + vCPU count
- RAM total (MB)
- Disk summary
- Network interfaces + primary IP
- Key packages installed (curated list: openssh-server, ufw/nftables, fail2ban, docker, python3, rsync, curl, git, sudo)

The YAML output includes:
- `identity`: name, stage, region
- `access`: host, user, port, key
- `facts`: OS/CPU/RAM/disk/network + key packages
- `os.baseline`: placeholder for packages/sshd/firewall config

## MVP Slice

Start with one Hetzner VPS:

- Provision VPS + attach basic firewall rules
- Bootstrap non-root sudo user and disable password auth
- Install Docker, create `PW_NET`
- Deploy Traefik + one Postgres service with alias (e.g., `pg18`)
- Deploy one Odoo instance with rendered config and Traefik routing
- Push-only sync to `/var/lib/perfectwork` and run `doctor`

## First Implementation Milestone (Hetzner Create Only)

The first executable milestone is a Hetzner-only VPS creation flow:

- `cstation vps create --provider hetzner --name <name> --region <region> --type <type> --image <image> --ssh-key <key>`
- `cstation vps ls --provider hetzner`
- `cstation vps status <name-or-id> --provider hetzner`
- `cstation vps delete <name-or-id> --provider hetzner` (requires confirmation)
