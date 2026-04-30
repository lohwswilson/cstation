# Implementation Plan: Docker Service Management (Phase 1)

## Objective

Implement `cstation docker plan/apply/status` for Traefik + Portainer on eu01.synercatalyst.com, including the config directory migration from flat file to `config/vps/<name>/vps.yaml` + fragments.

## Prerequisites

- `cstation vps apply eu01.synercatalyst.com` has been run (Docker running, PW_NET exists)
- Specs finalized in `docs/superpowers/specs/2026-04-29-docker-service-management-design.md`

## Step 1: Config Directory Migration

### 1a. Migrate eu01 config
- Create directory: `config/vps/eu01.synercatalyst.com/`
- Move `config/vps/eu01.synercatalyst.com.yaml` → `config/vps/eu01.synercatalyst.com/vps.yaml`
- Delete old flat file
- Update `docker.directories` to add `/var/lib/traefik`, `/var/lib/portainer`

### 1b. Create fragment files
- `config/vps/eu01.synercatalyst.com/traefik.yaml` (kind: Container, enabled: true)
- `config/vps/eu01.synercatalyst.com/portainer.yaml` (kind: Container, enabled: true)
- `config/vps/eu01.synercatalyst.com/mailcow.yaml` (kind: Stack, enabled: false)

### 1c. Update VPS commands to accept directory path or VPS name
- `_load_vps_config()` in `src/cstation/commands/vps/main.py`:
  - If arg is a directory → look for `vps.yaml` inside
  - If arg is not a directory → treat as VPS name → search `config/vps/`
- Update `vps init` to write `config/vps/<name>/vps.yaml` instead of `config/vps/<name>.yaml`
- Update all existing VPS tests for new path resolution

### 1d. Migrate sg07 (when ready)
- Same pattern — not blocking for Phase 1

## Step 2: Docker Command Infrastructure

### 2a. Create service class infrastructure
- `src/cstation/commands/docker/services/__init__.py` — import all built-ins
- `src/cstation/commands/docker/services/base.py` — `ContainerService` protocol
- `src/cstation/commands/docker/services/registry.py` — `register_service`, `get_service`
- `src/cstation/commands/docker/services/image_service.py` — `ImageService` base (kind: Container)

### 2b. Create compose utilities
- `src/cstation/commands/docker/compose/__init__.py`
- `src/cstation/commands/docker/compose/render.py` — dict → compose YAML
- `src/cstation/commands/docker/compose/env_writer.py` — dict → `.env` file string

### 2c. Implement TraefikService
- `src/cstation/commands/docker/services/traefik.py`
- Extends `ImageService`
- Generates `docker-compose.yml` from fragment config (with `env_file: .env` for secrets)
- Generates `/var/lib/traefik/etc/traefik.yml` from `static_config`
- Creates subdirectories: `etc/`, `conf/`, `letsencrypt/`, `logs/`
- Writes `.env` secrets template on first apply (preserves existing `.env` on re-apply)
- Plan warns if secrets contain placeholder values

### 2d. Implement PortainerService
- `src/cstation/commands/docker/services/portainer.py`
- Extends `ImageService` (simple, no static config)

## Step 3: Docker CLI Commands

### 3a. Rewrite docker main.py
- Remove playbook import
- New `docker_app` with commands: `plan`, `apply`, `status`
- Accept `<vps>` argument (directory path or VPS name)
- Load `vps.yaml` for SSH config
- Discover fragment files
- Support `--service <name>` filter

### 3b. Implement `docker plan`
- Pre-flight: verify Docker running + PW_NET exists on the VPS
- Port collision detection across enabled fragments + running containers
- Orphan detection: running containers not in any fragment
- For each enabled fragment: compare declared vs actual state (compose file, configs, env, container state, network)
- Print summary

### 3c. Implement `docker apply`
- Same pre-flight + port check as plan
- For each enabled fragment (Traefik first):
  - Create directories on VPS
  - Write compose file + .env + static configs
  - Run `docker compose up -d`
  - Verify containers running
- Interactive confirmation (skip with `--yes`)
- Support `--service <name>` for single service
- Support `--prune` for orphan removal

### 3d. Implement `docker status`
- Table output: service, kind, enabled, state, image, ports, uptime
- For each enabled fragment: query `docker compose ps` on VPS

### 3e. Delete playbook.py
- Remove `src/cstation/commands/docker/playbook.py`
- Verify no other imports reference it

## Step 4: Tests

### 4a. VPS config migration tests
- Test `_load_vps_config()` with directory path
- Test `_load_vps_config()` with VPS name (auto-discover)
- Test `_discover_fragments()` (all `*.yaml` except `vps.yaml`)
- Test `vps init` writes to `config/vps/<name>/vps.yaml`

### 4b. Docker plan/apply tests
- Mock `SSHManager.run` with docker command responses
- Test fragment loading from temp directory
- Test TraefikService compose generation
- Test PortainerService compose generation
- Test pre-flight check (Docker not running → clear error)
- Test port collision detection
- Test idempotency (second apply shows "already configured")
- Test `--service` filter

## Step 5: Verify on eu01

```bash
# 1. Ensure vps apply is current
uv run cstation vps apply eu01.synercatalyst.com --yes

# 2. Plan Traefik
uv run cstation docker plan eu01.synercatalyst.com --service traefik

# 3. Apply Traefik
uv run cstation docker apply eu01.synercatalyst.com --service traefik --yes

# 4. Set Cloudflare secrets on VPS
ssh root@37.27.218.255 "vi /var/lib/traefik/.env"
# Set CF_API_EMAIL and CF_API_KEY to real values

# 5. Restart Traefik to pick up secrets
ssh root@37.27.218.255 "cd /var/lib/traefik && docker compose restart"

# 6. Verify Traefik running
ssh root@37.27.218.255 "docker compose -f /var/lib/traefik/docker-compose.yml ps"

# 7. Verify Traefik API (via SSH tunnel — no insecure dashboard)
ssh -L 8080:localhost:8080 root@37.27.218.255
# Then on local machine: curl -s http://localhost:8080/api/rawdata

# 8. Verify HTTPS redirect
curl -s -o /dev/null -w "%{http_code}" http://37.27.218.255
# Should return 301 (redirect to HTTPS)

# 9. Plan Portainer
uv run cstation docker plan eu01.synercatalyst.com --service portainer

# 10. Apply Portainer
uv run cstation docker apply eu01.synercatalyst.com --service portainer --yes

# 11. Verify Portainer running
ssh root@37.27.218.255 "docker compose -f /var/lib/portainer/docker-compose.yml ps"

# 12. Full status
uv run cstation docker status eu01.synercatalyst.com

# 13. Re-apply (idempotency check — should show "already configured")
uv run cstation docker apply eu01.synercatalyst.com --yes
```

## Files Changed (Summary)

### New files
- `config/vps/eu01.synercatalyst.com/traefik.yaml`
- `config/vps/eu01.synercatalyst.com/portainer.yaml`
- `config/vps/eu01.synercatalyst.com/mailcow.yaml`
- `src/cstation/commands/docker/services/__init__.py`
- `src/cstation/commands/docker/services/base.py`
- `src/cstation/commands/docker/services/registry.py`
- `src/cstation/commands/docker/services/image_service.py`
- `src/cstation/commands/docker/services/traefik.py`
- `src/cstation/commands/docker/services/portainer.py`
- `src/cstation/commands/docker/compose/__init__.py`
- `src/cstation/commands/docker/compose/render.py`
- `src/cstation/commands/docker/compose/env_writer.py`
- `tests/commands/test_docker_cli.py`

### Modified files
- `config/vps/eu01.synercatalyst.com.yaml` → moved to `config/vps/eu01.synercatalyst.com/vps.yaml`
- `src/cstation/commands/docker/main.py` (rewrite)
- `src/cstation/commands/vps/main.py` (update config loading for directory paths)
- `tests/commands/test_vps_cli.py` (update for new config path)

### Deleted files
- `config/vps/eu01.synercatalyst.com.yaml` (old flat file)
- `src/cstation/commands/docker/playbook.py` (retired)