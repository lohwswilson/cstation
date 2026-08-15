# CStation Configuration Guide

This guide explains how CStation locates, loads, and validates configuration files for servers, containers, DNS zones, images, and GitHub repositories.

---

## Configuration Hierarchy

CStation discovers configuration files in the following directory order (highest precedence wins):

1. **`./etc/`** — Project-local override directory.
2. **`/etc/cstation/`** — System-wide configuration directory.
3. **`~/.config/cstation/`** — User-level directory (Default source of truth).

---

## Directory Layout

A standard `~/.config/cstation/` directory is structured as follows:

```
~/.config/cstation/
├── config.yaml                     # Global settings & provider credentials
│
├── vps/                            # VPS servers and container stacks
│   ├── sg01.synercatalyst.com/
│   │   ├── vps.yaml                # VPS definition (access, OS baseline, docker)
│   │   ├── .facts.json             # Cached hardware metrics (<100ms status)
│   │   ├── traefik.yaml            # Container fragment (Reverse proxy)
│   │   ├── db.yaml                 # Container fragment (PostgreSQL)
│   │   └── sg01_prod.yaml          # Container fragment (Odoo ERP)
│   │
│   └── us02.synercatalyst.com/
│       ├── vps.yaml
│       └── ...
│
├── dns/                            # Declarative DNS zones
│   ├── synercatalyst.com.yaml      # DNS records for synercatalyst.com
│   └── ansis.com.sg.yaml
│
├── github/                         # GitHub repository mappings
│   └── odoo_repos.sync.yml         # Odoo & OpenUpgrade sync definitions
│
└── images/                         # Docker image build configurations
    └── synercatalyst-odoo.13.0/
        ├── Dockerfile
        └── image.yaml
```

---

## 1. Global Settings (`config.yaml`)

Defines cloud provider API credentials, secrets, and global defaults.

```yaml
# Cloud provider credentials
vps:
  default_provider: static
  providers:
    hetzner:
      accounts:
        ANSIS:
          token: "your-hetzner-api-token"
    vultr:
      api_key: "your-vultr-api-key"

# Cloudflare DNS API Token
cloudflare:
  api_token: "your-cloudflare-api-token"

# Container & Service Secrets (Injected during apply/plan)
vps:
  secrets:
    sg01.synercatalyst.com:
      traefik:
        CF_API_EMAIL: "admin@example.com"
        CF_API_KEY: "secret-cloudflare-key"
      sg01_prod:
        PASSWORD: "super-secure-db-password"
```

---

## 2. VPS Configuration (`vps/<hostname>/vps.yaml`)

Defines the server identity, SSH access, baseline OS security settings, and Docker daemon configuration.

```yaml
apiVersion: cstation/v1
kind: VPS

identity:
  name: sg01.synercatalyst.com
  stage: prod
  region: singapore
  provider: static

access:
  host: 192.168.1.100
  port: 22
  user: root
  key: ~/.ssh/id_rsa

os:
  baseline:
    packages:
      - curl
      - htop
      - ufw
      - fail2ban
      - rsync
    upgrade_all: false
    sshd:
      port: 22
      permit_root_login: "prohibit-password"
      password_authentication: false
    firewall:
      enabled: true
      default_incoming: "deny"
      allow:
        - "22/tcp"
        - "80/tcp"
        - "443/tcp"
    swap:
      size_mb: 4096
      swappiness: 10
    tuning:
      sysctl:
        vm.max_map_count: 262144
        net.core.somaxconn: 1024

docker:
  daemon:
    log_driver: "json-file"
    log_opts:
      max-size: "50m"
      max-file: "3"
  networks:
    - PW_NET
  directories:
    - /var/lib/perfectwork
    - /srv/data
```

---

## 3. Container Fragment (`vps/<hostname>/<name>.yaml`)

Declarative container fragment placed alongside `vps.yaml`.

```yaml
apiVersion: cstation/v1
kind: Container
name: SG01_PROD
image: synercatalyst/odoo:18.0
restart: always
network: PW_NET

ports:
  - "8069:8069"

volumes:
  - /var/lib/perfectwork/PW.18.0:/usr/lib/python3/dist-packages/odoo
  - /var/lib/perfectwork/PW_ADDONS.18.0:/mnt
  - /var/lib/perfectwork/SG01/CONTAINERS/SG01_PROD:/var/lib/odoo

env:
  HOST: SG01_DB
  PORT: 5432
  USER: odoo
  PASSWORD: ${PASSWORD}

labels:
  traefik.enable: "true"
  traefik.http.routers.sg01_prod.rule: "Host(`erp.synercatalyst.com`)"
  traefik.http.routers.sg01_prod.entrypoints: "websecure"
  traefik.http.routers.sg01_prod.tls.certresolver: "le_resolver"

odoo_conf:
  db_host: SG01_DB
  db_user: odoo
  limit_time_cpu: 600
  limit_time_real: 1200
  workers: 4
```

---

## 4. DNS Declarations (`dns/<domain>.yaml`)

Declarative DNS record configuration managed by `cstation dns`.

```yaml
apiVersion: cstation/v1
kind: DNS
domain: synercatalyst.com

records:
  - name: "@"
    type: A
    value: "192.168.1.100"
    proxied: true
    ttl: 1

  - name: "erp"
    type: CNAME
    value: "synercatalyst.com"
    proxied: true

  - name: "@"
    type: MX
    value: "mail.synercatalyst.com"
    priority: 10
    ttl: 3600

  - name: "_autodiscover._tcp"
    type: SRV
    value: "mail.synercatalyst.com"
    priority: 0
    srv_weight: 0
    srv_port: 443
    ttl: 3600
```

---

## 5. GitHub Repositories (`github/odoo_repos.sync.yml`)

Maps Odoo, OpenUpgrade, and module repositories for multi-branch upstream synchronization and deployment.

```yaml
github:
  username: lohwswilson
  default_clone_method: ssh
  default_directory: /opt/PW

repositories:
  - name: PW.18.0
    description: "PerfectWork 18.0 (ansis-ai/odoo)"
    branch: "18.0"
    category: odoo
    auto_sync: true
    local_path: /opt/PW/PW.18.0
    upstream_url: git@github.com:odoo/odoo.git

  - name: OpenUpgrade_18.0
    description: "OpenUpgrade 18.0 (ansis-ai/OpenUpgrade)"
    branch: "18.0"
    category: openupgrade
    auto_sync: true
    local_path: /opt/PW/OpenUpgrade_18.0
    upstream_url: https://github.com/OCA/OpenUpgrade.git
```
