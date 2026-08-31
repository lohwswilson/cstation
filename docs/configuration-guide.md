# CStation Configuration Guide ⚙️

This guide explains how CStation discovers, loads, and validates configuration files for VPS instances, container fragments, DNS zones, images, and secrets.

---

## 📑 Table of Contents

1. [Configuration Discovery & Precedence](#1-configuration-discovery--precedence)
2. [Directory Layout](#2-directory-layout)
3. [Global Settings & Secrets (`config.yaml`)](#3-global-settings--secrets-configyaml)
4. [VPS Infrastructure Schema (`vps.yaml`)](#4-vps-infrastructure-schema-vpsyaml)
5. [Container Fragment Schema (`<service>.yaml`)](#5-container-fragment-schema-serviceyaml)
   - [Odoo ERP Service Extension](#odoo-erp-service-extension)
   - [Traefik Reverse Proxy Extension](#traefik-reverse-proxy-extension)
6. [DNS Zone Schema (`dns/<domain>.yaml`)](#6-dns-zone-schema-dnsdomainyaml)
7. [Multi-Arch Image Build Schema (`image.yaml`)](#7-multi-arch-image-build-schema-imageyaml)

---

## 1. Configuration Discovery & Precedence

CStation merges configuration files from three locations using local-first precedence (**highest precedence first**):

1. **`~/.config/cstation/`** (User Directory) — **Highest Priority** (Default source of truth).
2. **`/etc/cstation/`** (System Directory) — Medium Priority.
3. **`./etc/`** (Bundled Fallback) — Lowest Priority.

---

## 2. Directory Layout

A standard `~/.config/cstation/` directory layout:

```
~/.config/cstation/
├── config.yaml                     # Global credentials & secrets
├── vps/                            # VPS servers and container stacks
│   ├── sg01.synercatalyst.com/
│   │   ├── vps.yaml                # VPS hardware, access, & OS baseline
│   │   ├── .facts.json             # Cached hardware metrics (<100ms status)
│   │   ├── SG01_DB.yaml            # PostgreSQL container fragment
│   │   ├── SG01_TRAEFIK.yaml       # Traefik reverse proxy fragment
│   │   ├── SG01_PORTAINER.yaml     # Portainer CE fragment
│   │   └── SG01_DEV8_SG01DB.yaml   # Odoo 18 container stack fragment
│   └── us01.synercatalyst.com/
├── dns/                            # Declarative DNS zones (synercatalyst.com.yaml)
├── github/                         # Git repository sync definitions (odoo_repos.sync.yml)
└── images/                         # Multi-arch Docker image build recipes
```

---

## 3. Global Settings & Secrets (`config.yaml`)

Defines cloud provider API credentials, DNS tokens, and container secrets:

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

# Injected container secrets (never commit to public repos)
secrets:
  sg01.synercatalyst.com:
    SG01_DB:
      POSTGRES_PASSWORD: "secret-db-password"
    SG01_DEV8_SG01DB:
      PASSWORD: "secret-user-password"
      PGPASSWORD: "secret-user-password"
    SG01_TRAEFIK:
      CF_API_EMAIL: "admin@example.com"
      CF_API_KEY: "secret-cloudflare-key"
```

---

## 4. VPS Infrastructure Schema (`vps.yaml`)

```yaml
apiVersion: cstation/v1
kind: VPS

identity:
  name: sg01.synercatalyst.com
  stage: prod
  region: singapore
  provider: static

access:
  host: 107.155.65.47
  user: root
  port: 22
  key: ~/.ssh/id_ed25519

os:
  baseline:
    packages:
      - ufw
      - fail2ban
      - docker.io
      - docker-compose-v2
      - containerd
      - rsync
      - git
      - curl
      - sudo
    sshd:
      disable_password_auth: true
    firewall:
      mode: ufw
      allow:
        - 22/tcp
    swap:
      size_gb: 8
    tuning:
      bbr: true
      vm_swappiness: 10
      net_core_somaxconn: 4096
      net_ipv4_tcp_tw_reuse: 1
      nofile: 65536
    journald:
      system_max_use: 500M
    fail2ban:
      bantime: 1h
      findtime: 10m
      maxretry: 5

docker:
  daemon:
    log_driver: json-file
    log_opts:
      max-size: 10m
      max-file: '3'
    live_restore: true
  networks:
    - PW_NET
  directories:
    - /var/lib/postgresql
    - /var/lib/traefik
    - /var/lib/perfectwork
```

---

## 5. Container Fragment Schema (`<service>.yaml`)

### Basic Container Fragment
```yaml
apiVersion: cstation/v1
kind: Container
name: SG01_DB
enabled: true
image: pgvector/pgvector:pg18
container_name: SG01_DB
network: PW_NET
ports:
  - "127.0.0.1:1488:5432"
volumes:
  - "/var/lib/postgresql:/var/lib/postgresql/data"
secrets:
  - POSTGRES_PASSWORD
env:
  POSTGRES_USER: postgres
  PGDATA: /var/lib/postgresql/data/pgdata
restart_policy: always
```

### Odoo ERP Service Extension
```yaml
apiVersion: cstation/v1
kind: Container
name: SG01_DEV8_SG01DB
enabled: true
image: synercatalyst/odoo.18.0:latest
container_name: SG01_DEV8_SG01DB
network: PW_NET
owner: "100:101"
chmod: "755"
ports:
  - 3348:8069
  - 3347:8072
volumes:
  - /var/lib/perfectwork/PW.18.0/odoo:/usr/lib/python3/dist-packages/odoo
  - /var/lib/perfectwork/PW.18.0/addons:/mnt/extra-addons
  - /var/lib/perfectwork/SG01/CONTAINERS/SG01_DEV8_SG01DB:/var/lib/odoo
  - /var/lib/perfectwork/PW_ADDONS.18.0:/mnt
secrets:
  - PASSWORD
  - PGPASSWORD
env:
  HOST: SG01_DB
  PORT: '5432'
  USER: sg01_dev8_sg01db
  ODOO_RC: /var/lib/odoo/odoo.conf
  LANG: en_US.UTF-8
  ODOO_VERSION: '18.0'
odoo_conf:
  db_host: SG01_DB
  db_port: 5432
  db_user: sg01_dev8_sg01db
  dbfilter: ^%d$
  admin_passwd: secret-master-password
  db_maxconn: 32
  addons_path: /mnt/extra-addons, /mnt/ansis, /mnt/OCA, /mnt/customers
  server_wide_modules: web, queue_job, fastapi
  log_level: info
  workers: 5
  max_cron_threads: 2
  limit_time_cpu: 1800
  limit_time_real: 3600
traefik:
  http:
    routers:
      sg01-dev8-web:
        entryPoints: [web, websecure]
        service: sg01-dev8-service
        rule: HostRegexp(`^[a-z0-9]+\.dev8\.perfectwork\.app$`)
        tls:
          certResolver: le_dns_resolver
          domains:
            - main: dev8.perfectwork.app
              sans: '*.dev8.perfectwork.app'
      sg01-dev8-ws:
        entryPoints: [web, websecure]
        service: sg01-dev8-ws-service
        rule: HostRegexp(`^[a-z0-9]+\.dev8\.perfectwork\.app$`) && PathPrefix(`/websocket`)
        middlewares: [upgradeheader, sslheader]
        tls:
          certResolver: le_dns_resolver
          domains:
            - main: dev8.perfectwork.app
              sans: '*.dev8.perfectwork.app'
    services:
      sg01-dev8-service:
        loadBalancer:
          servers: [{ url: "http://SG01_DEV8_SG01DB:8069" }]
      sg01-dev8-ws-service:
        loadBalancer:
          servers: [{ url: "http://SG01_DEV8_SG01DB:8072" }]
    middlewares:
      sslheader:
        headers:
          customRequestHeaders: { X-Forwarded-Proto: "https" }
      upgradeheader:
        headers:
          customRequestHeaders: { Connection: "Upgrade", Upgrade: "websocket" }
          forceSTSHeader: true
          hostsProxyHeaders: ["websocket", "Upgrade"]
restart_policy: always
```

---

## 6. DNS Zone Schema (`dns/<domain>.yaml`)

```yaml
apiVersion: cstation/v1
kind: DNS
domain: synercatalyst.com

records:
  - name: sg01
    type: A
    value: 107.155.65.47
    ttl: 300
    proxied: false

  - name: "*.dev8"
    type: A
    value: 107.155.65.47
    ttl: 300

  - name: mail
    type: A
    value: 152.53.169.95
    ttl: 300

  - name: ""
    type: MX
    value: mail.ansis.com.sg
    priority: 10
    ttl: 300
```

---

## 7. Multi-Arch Image Build Schema (`image.yaml`)

```yaml
apiVersion: cstation/v1
kind: DockerImage
name: synercatalyst-odoo.13.0

image:
  repository: synercatalyst/odoo.13.0
  tags:
    - "13.0"
    - "latest"

build:
  context: .
  dockerfile: Dockerfile
  platforms:
    - linux/amd64
    - linux/arm64
  args:
    ODOO_VERSION: "13.0"
```
