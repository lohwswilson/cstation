# CStation: End-to-End VPS-to-Odoo Setup Guide

This guide walks through provisioning a new VPS, hardening the OS, deploying Docker infrastructure, and bringing up a production Odoo instance with Traefik routing and PostgreSQL — all managed declaratively through CStation.

## Overview

CStation manages infrastructure as code from your local machine. Your `~/.config/cstation/` directory is the single source of truth. All changes are previewable via `plan` before `apply`.

The full journey takes ~15-20 minutes end-to-end once the VPS is provisioned:

```
VPS Provisioned → vps init → customize vps.yaml → vps apply (OS + Docker)
                                                         ↓
    Odoo running ← docker apply (containers) ← create fragment YAMLs
```

---

## 1. Prerequisites

### On your local machine
- **Python 3.13+** and **[uv](https://docs.astral.sh/uv/)** package manager
- **Git** to clone the repository
- **SSH key pair** for VPS access (`~/.ssh/id_rsa` or similar)

### External accounts & tokens
- **Hetzner Cloud** account (if using Hetzner) with an API token
- **Cloudflare** account with an API token (for DNS management)
- **Docker Hub** credentials (for pulling private images)

### On the VPS
- A supported Linux distribution: Ubuntu 22.04/24.04, Debian 12, Rocky Linux 9, or Alpine 3.20+
- Root or sudo-capable user with SSH key-based access
- Public IPv4 address

---

## 2. Install CStation

```bash
git clone git@github.com:your-org/cstation.git
cd cstation
uv pip install -e .
uv run cstation --help
```

---

## 3. One-Time Global Configuration

Create `~/.config/cstation/config.yaml`:

```yaml
# ── Provider tokens ────────────────────────────────────────────
vps:
  default_provider: hetzner
  providers:
    hetzner:
      accounts:
        personal:
          token: "your-hetzner-api-token"

# ── Cloudflare DNS ─────────────────────────────────────────────
cloudflare:
  api_token: "your-cloudflare-api-token"

# ── Docker Hub (for image build/push) ──────────────────────────
docker_hub:
  username: "your-username"
  token: "your-docker-hub-token"

# ── Secrets (DB passwords, admin credentials) ──────────────────
# These are injected into container .env files at deploy time.
# Add entries per VPS + service as you create fragments (Section 8).
  secrets:
    sg01.example.com:
      SG01_DB:
        POSTGRES_PASSWORD: "secure-db-password"
      SG01_ODOO:
        PASSWORD: "odoo-db-password"
```

Set restrictive permissions:

```bash
chmod 600 ~/.config/cstation/config.yaml
```

Optionally, create `~/.config/cstation/.env` for the Hetzner token (useful in CI):

```env
HETZNER_TOKEN=your-hetzner-api-token
```

---

## 4. Provision the VPS (Hetzner Example)

If your VPS is already provisioned, skip to Section 5.

For Hetzner, create the server through the Cloud Console or API. Recommended minimum specs for a production Odoo instance:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| vCPU | 2 | 4+ |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB | 80 GB |
| OS | Ubuntu 24.04 | Ubuntu 24.04 |

Important: upload your SSH public key during creation so root key-based auth works immediately.

---

## 5. Initialize VPS Config

`vps init` connects via SSH, collects hardware/OS facts, and writes a starter `vps.yaml`. It is **read-only** — no changes are made to the server.

### From a cloud provider

```bash
# Hetzner VPS by server ID
uv run cstation vps init hetzner/personal:12345678 --stage prod

# Hetzner VPS by name
uv run cstation vps init hetzner/personal:sg01.example.com --stage prod
```

### Static provider (any server with SSH)

```bash
uv run cstation vps init 1.2.3.4 --port 22 --user root
```

This creates:

```
~/.config/cstation/vps/
└── sg01.example.com/
    └── vps.yaml    ← identity, access, facts, baseline
```

---

## 6. Customize `vps.yaml`

Open `~/.config/cstation/vps/sg01.example.com/vps.yaml` and adjust the baseline. Key sections to review:

```yaml
apiVersion: cstation/v1
kind: VPS
identity:
  name: sg01.example.com
  stage: prod
  region: sg
  provider: hetzner

access:
  host: 1.2.3.4
  user: root
  port: 22

os:
  hostname: sg01.example.com
  baseline:
    upgrade_all: false       # set to true first time to upgrade all packages
    packages:
      - fail2ban
      - docker.io
      - ufw
      - nftables
    shell: zsh
    terminal: xterm-256color
    sshd:
      disable_password_auth: true
    firewall:
      mode: ufw
      allow:
        - 22/tcp
        - 80/tcp
        - 443/tcp
    swap:
      size_gb: 4
    tuning:
      vm_swappiness: 10
      vm_overcommit_memory: 1
      net_ipv4_tcp_max_syn_backlog: 4096
      fs_inotify_max_user_watches: 524288
      net_ipv4_tcp_keepalive_time: 600
    fail2ban:
      bantime: 10m
      findtime: 10m
      maxretry: 5
  journald:
    system_max_use: 500M
    forward_to_syslog: false

docker:
  daemon:
    log_driver: json-file
    log_opts:
      max-size: 10m
      max-file: 3
    storage_driver: overlay2
    live_restore: true
    iptables: true
  networks:
    - PW_NET                  # shared Docker network for services
  directories:
    - /var/lib/perfectwork    # root for PW/Odoo data & addons
```

---

## 7. Apply OS & Docker Infrastructure

### Preview

```bash
uv run cstation vps plan sg01.example.com
```

This dry-runs all 13 phases and shows exactly what will change.

### Apply

```bash
uv run cstation vps apply sg01.example.com --yes
```

The 13-phase pipeline runs sequentially:

| # | Phase | What happens |
|---|-------|-------------|
| 1 | `upgrade_all` | `apt upgrade` all packages (if enabled) |
| 2 | `packages` | Install missing packages (fail2ban, docker.io, ufw, etc.) |
| 3 | `shell` | Install and set default shell (zsh) |
| 4 | `terminal` | Set `TERM=xterm-256color` in `/etc/environment` |
| 5 | `sshd` | Disable password authentication |
| 6 | `firewall` | Enable UFW, open ports 22, 80, 443 |
| 7 | `swap` | Create and enable swap file |
| 8 | `tuning` | Apply sysctl kernel params + journald config |
| 9 | `fail2ban` | Configure SSH jail and restart fail2ban |
| 10 | `hostname` | Set server hostname |
| 11 | `docker_daemon` | Write `/etc/docker/daemon.json` and restart Docker |
| 12 | `docker_networks` | Create `PW_NET` Docker network |
| 13 | `docker_directories` | Create `/var/lib/perfectwork` |

To run a single phase (e.g., after editing firewall rules):

```bash
uv run cstation vps apply sg01.example.com --phase firewall --yes
```

---

## 8. Create Container Fragment YAMLs

Fragments are individual YAML files in the VPS directory. They are processed **alphabetically**, which determines startup order. Name them so dependencies come first.

### 8a. Traefik (Reverse Proxy)

Create `~/.config/cstation/vps/sg01.example.com/A_TRAEFIK.yaml`:

```yaml
apiVersion: cstation/v1
kind: Container
name: sg01-traefik
enabled: true
image: traefik:v3.1
container_name: sg01-traefik
network: PW_NET
restart_policy: always
ports:
  - 80:80
  - 443:443
volumes:
  - /var/lib/traefik:/etc/traefik
  - /var/run/docker.sock:/var/run/docker.sock:ro
command:
  - --providers.docker=true
  - --providers.docker.network=PW_NET
  - --providers.docker.exposedbydefault=false
  - --providers.file.directory=/etc/traefik/conf
  - --entrypoints.web.address=:80
  - --entrypoints.websecure.address=:443
  - --certificatesresolvers.le_resolver.acme.tlschallenge=true
  - --certificatesresolvers.le_resolver.acme.email=admin@example.com
  - --certificatesresolvers.le_resolver.acme.storage=/etc/traefik/acme.json
  - --certificatesresolvers.le_dns_resolver.acme.dnschallenge.provider=cloudflare
  - --certificatesresolvers.le_dns_resolver.acme.email=admin@example.com
  - --certificatesresolvers.le_dns_resolver.acme.storage=/etc/traefik/acme-dns.json
env:
  CF_API_EMAIL: admin@example.com
secrets:
  - CF_API_KEY
labels:
  traefik.enable: "true"
  traefik.http.middlewares.compress.compress: "true"
  traefik.http.middlewares.sslheader.headers.customrequestheaders.X-Forwarded-Proto: "https"
```

Add the Cloudflare API key secret to `~/.config/cstation/config.yaml`:

```yaml
vps:
  secrets:
    sg01.example.com:
      sg01-traefik:
        CF_API_KEY: "your-cloudflare-api-key"
```

### 8b. PostgreSQL

Create `~/.config/cstation/vps/sg01.example.com/B_DB.yaml`:

```yaml
apiVersion: cstation/v1
kind: Container
name: sg01-db
enabled: true
image: postgres:16
container_name: sg01-db
network: PW_NET
restart_policy: always
ports:
  - 127.0.0.1:5432:5432     # localhost-only, remote access via SSH tunnel
volumes:
  - /var/lib/perfectwork/sg01-db:/var/lib/postgresql/data
env:
  POSTGRES_DB: postgres
  PGDATA: /var/lib/postgresql/data/pgdata
secrets:
  - POSTGRES_PASSWORD
command:
  - postgres
  - -c
  - shared_buffers=2GB       # tune to ~25% of available RAM
  - -c
  - effective_cache_size=6GB # tune to ~75% of available RAM
  - -c
  - max_connections=200
  - -c
  - work_mem=16MB
  - -c
  - maintenance_work_mem=512MB
```

Add the DB password secret to `~/.config/cstation/config.yaml`:

```yaml
vps:
  secrets:
    sg01.example.com:
      sg01-db:
        POSTGRES_PASSWORD: "secure-postgres-password"
```

### 8c. Odoo Application

Create `~/.config/cstation/vps/sg01.example.com/C_ODOO.yaml`:

```yaml
apiVersion: cstation/v1
kind: Container
name: sg01-odoo
enabled: true
image: synercatalyst/odoo.18.0:latest
container_name: sg01-odoo
network: PW_NET
restart_policy: always
ports:
  - 8069:8069
  - 8072:8072
volumes:
  - /var/lib/perfectwork/PW_ADDONS.18.0:/mnt
  - /var/lib/perfectwork/sg01-odoo-data:/var/lib/odoo
  - /var/lib/perfectwork/PW.18.0:/usr/lib/python3/dist-packages/odoo
env:
  HOST: sg01-db               # must match the DB container_name
  PORT: '5432'
  USER: sg01_odoo
  ODOO_RC: /var/lib/odoo/odoo.conf
  LANG: en_US.UTF-8
  ODOO_VERSION: '18.0'
secrets:
  - PASSWORD                   # resolved from config.yaml secrets
labels:
  traefik.enable: "true"
  traefik.http.routers.sg01-odoo.entrypoints: websecure
  traefik.http.routers.sg01-odoo.rule: Host(`erp.example.com`)
  traefik.http.routers.sg01-odoo.tls: "true"
  traefik.http.routers.sg01-odoo.tls.certresolver: le_resolver
  traefik.http.routers.sg01-odoo.middlewares: compress,sslheader
  traefik.http.services.sg01-odoo.loadbalancer.server.port: "8069"
  # Websocket/longpolling router
  traefik.http.routers.sg01-odoo-ws.entrypoints: websecure
  traefik.http.routers.sg01-odoo-ws.rule: "Host(`erp.example.com`) && (PathPrefix(`/websocket`) || PathPrefix(`/longpolling`))"
  traefik.http.routers.sg01-odoo-ws.tls: "true"
  traefik.http.routers.sg01-odoo-ws.tls.certresolver: le_resolver
  traefik.http.routers.sg01-odoo-ws.middlewares: compress,sslheader
  traefik.http.services.sg01-odoo-ws.loadbalancer.server.port: "8072"

# Odoo configuration rendered to odoo.conf
odoo_conf:
  db_host: sg01-db
  db_port: 5432
  db_user: sg01_odoo
  dbfilter: ".*"              # or a specific pattern like "PROD*"
  admin_passwd: "change-me"
  db_maxconn: 64
  addons_path: /mnt
  server_wide_modules: web
  log_level: info
  workers: 5                  # ~1 per vCPU
  max_cron_threads: 2
  limit_memory_soft: 2147483648
  limit_memory_hard: 2684354560
  limit_request: 8192
  limit_time_cpu: 1800
  limit_time_real: 3600

# Auto-create database at deploy time
odoo_db:
  name: PROD
  owner: sg01_odoo

# Odoo container runs as UID 101 (odoo user), GID 102
owner: "101:102"
chmod: "766"
```

Add the Odoo DB password secret:

```yaml
vps:
  secrets:
    sg01.example.com:
      sg01-odoo:
        PASSWORD: "odoo-database-password"
```

### Final directory layout

```
~/.config/cstation/vps/sg01.example.com/
├── vps.yaml
├── A_TRAEFIK.yaml
├── B_DB.yaml
└── C_ODOO.yaml
```

---

## 9. Deploy Container Services

### Preview

```bash
uv run cstation docker plan sg01.example.com
```

Shows what containers will be created/updated, including the generated `odoo.conf`, DB user, and database.

### Deploy in order

If deploying for the first time, do them sequentially to respect dependencies:

```bash
# 1. Traefik (must be running before Odoo for routing)
uv run cstation docker apply sg01.example.com --service sg01-traefik --yes

# 2. PostgreSQL (Odoo needs it for DB user/database creation)
uv run cstation docker apply sg01.example.com --service sg01-db --yes

# 3. Odoo (creates PG user + database, writes odoo.conf, then starts container)
uv run cstation docker apply sg01.example.com --service sg01-odoo --yes
```

For subsequent updates, deploy all at once:

```bash
uv run cstation docker apply sg01.example.com --yes
```

### Verify

```bash
uv run cstation docker status sg01.example.com
```

All three containers should show as running.

---

## 10. Sync Odoo Source Code & Addons

If using the PerfectWork framework, sync the PW source code and addons to the VPS:

```bash
uv run cstation odoo sync sg01 18.0 --port 22
```

This rsyncs from local `/opt/PW/` to the VPS directories mounted into the Odoo container.

For a dry-run first:

```bash
uv run cstation odoo sync sg01 18.0 --dry-run --verbose
```

---

## 11. DNS Setup

Create `~/.config/cstation/dns/example.com.yaml`:

```yaml
apiVersion: cstation/v1
kind: DNS
domain: example.com
records:
  - name: erp
    type: A
    value: 1.2.3.4     # VPS public IP
    ttl: 1
    proxied: false      # set true to proxy through Cloudflare
  - name: "@"
    type: A
    value: 1.2.3.4
    ttl: 1
    proxied: true
```

Preview and apply:

```bash
uv run cstation cloudflare plan example.com
uv run cstation cloudflare apply example.com --yes
```

Wait for DNS propagation (typically 1-5 minutes for non-proxied records). Verify:

```bash
dig +short erp.example.com
```

---

## 12. Verify Odoo is Running

```bash
# Check container status
uv run cstation docker status sg01.example.com --service sg01-odoo

# Check Odoo is responding
curl -I https://erp.example.com
```

Open `https://erp.example.com` in a browser. You should see the Odoo database selector (or login screen if a database exists).

### If no database exists

Odoo creates databases on first access. Go to `https://erp.example.com/web/database/manager` or use the database selector page. The `odoo_db` fragment key auto-creates the database at deploy time, so there should already be one.

---

## 13. Database Backup & Restore

### Download a backup from a running instance

```bash
uv run cstation odoo backup sg01.example.com sg01-odoo PROD
```

Downloads the latest `auto_backup` zip to your current directory.

### Restore a backup to a VPS

```bash
uv run cstation odoo restore sg01.example.com sg01-odoo backup.zip --dest-db PROD_RESTORED --yes
```

This creates the database, imports the SQL dump, restores the filestore, and fixes file ownership.

---

## 14. Day-to-Day Operations

```bash
# Check server health (load, RAM, disk, Docker status)
uv run cstation vps status sg01.example.com

# Force live refresh (bypasses cache)
uv run cstation vps status sg01.example.com --refresh

# List all VPSes with cached health metrics
uv run cstation vps list

# Preview changes before applying
uv run cstation docker plan sg01.example.com

# Apply changes to a specific service only
uv run cstation docker apply sg01.example.com --service sg01-odoo --yes

# Import an existing container from VPS into a fragment
uv run cstation docker import sg01.example.com my-container --name my-container
```

---

## 15. Troubleshooting

### SSH connection fails

```bash
# Test SSH directly
ssh -p 22 root@1.2.3.4 echo ok

# Check key path in vps.yaml
grep 'key:' ~/.config/cstation/vps/sg01.example.com/vps.yaml
```

### Docker network creation fails

```bash
# Check existing networks
ssh root@1.2.3.4 docker network ls
```

### Odoo container starts but can't reach DB

```bash
# Verify both are on PW_NET
ssh root@1.2.3.4 docker network inspect PW_NET

# Ping from Odoo to DB by container name
ssh root@1.2.3.4 docker exec sg01-odoo ping -c 1 sg01-db
```

### Schema validation errors

CStation validates all config with Pydantic. Errors include the file, field path, and message:

```
✗ Schema validation failed for vps/sg01.example.com/C_ODOO.yaml:
  - odoo_conf.db_host: Field required
  - env.HOST: Field required
```

Fix the named fields in the named file and retry.

### UFW blocking container ports

Don't open container ports in UFW — Docker manages iptables rules directly. UFW should only manage SSH (22) and the HTTP/HTTPS ports (80, 443) for Traefik.

---

## Summary

| Step | Command | Duration |
|------|---------|----------|
| Install | `uv pip install -e .` | 30s |
| Global config | Create `~/.config/cstation/config.yaml` | 5m |
| VPS init | `cstation vps init ...` | 10s |
| Customize vps.yaml | Edit file | 5m |
| Apply OS+Docker | `cstation vps apply ... --yes` | 3-5m |
| Create fragments | 3 YAML files | 10m |
| Deploy containers | `cstation docker apply ... --yes` | 2m |
| Sync Odoo code | `cstation odoo sync ...` | 1-5m |
| DNS | `cstation cloudflare apply ... --yes` | 1m |
| **Total** | | **~30m** |
