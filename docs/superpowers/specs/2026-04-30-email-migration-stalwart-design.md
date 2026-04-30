# Email Migration: Mailcow (us01) → Stalwart (eu01) Design

## Summary

Migrate email services from us01 (Mailcow, 21 containers, 4GB+ RAM) to eu01 (Stalwart, single container, 1-2GB RAM) using `cstation docker apply`. Stalwart replaces Mailcow as the mail server, with Traefik routing HTTP traffic and Stalwart binding SMTP/IMAP ports directly.

**Source**: us01.synercatalyst.com (209.182.236.52:8288) — Mailcow on `/var/lib/mailcow/`
**Target**: eu01.synercatalyst.com (37.27.218.255) — Stalwart in Docker

## Goals

- Replace Mailcow with Stalwart Mail Server on eu01
- Single Docker container instead of 21 (lower resource usage, simpler management)
- Route HTTP (admin UI, JMAP) through Traefik
- Stalwart binds SMTP/IMAP ports directly (no Traefik proxy for mail)
- Stalwart obtains its own TLS certificates via ACME DNS-01 (Cloudflare)
- Migrate 18 mailboxes across 7 domains (~13GB total) via `imapsync`
- Manage Stalwart declaratively via cstation fragment files

## Non-Goals

- Hot-swapping us01→eu01 without any downtime (brief cutover per domain)
- Migrating SOGo contacts/calendars automatically (users export/import manually)
- Implementing `kind: Stack` support in cstation (Stalwart is `kind: Container`)
- Multi-server clustering or distributed deployment

## Architecture

```
                    ┌────────────────────────────────────────┐
                    │      eu01 (37.27.218.255)              │
                    │                                        │
  Browser ──:443──► │  Traefik (PW_NET)                     │
  (HTTPS)           │    → HTTP → Stalwart:8080 (admin/JMAP)│
                    │    Obtains: *.synercatalyst.com cert   │
                    │                                        │
  Mail ────:25────► │  Stalwart (direct host ports)         │
  Client ───:465───►│    SMTP, SMTPS, Submission, IMAPS,    │
  ──:587, :993─────►│    POP3S, ManageSieve                │
                    │    Obtains: mail.perfectwork.app cert  │
                    │    via Cloudflare DNS-01 ACME         │
                    │                                        │
                    │  Portainer (PW_NET)                    │
                    │    :9000, :9443, :8000                  │
                    └────────────────────────────────────────┘
```

Port allocation on eu01:

| Port | Protocol | Service | Bound By |
|------|----------|---------|----------|
| 80 | HTTP | Traefik (redirect to HTTPS) | Traefik |
| 443 | HTTPS | Traefik (admin UI, JMAP) | Traefik |
| 25 | SMTP | Stalwart (inbound/outbound) | Stalwart |
| 110 | POP3 | Stalwart (legacy) | Stalwart |
| 465 | SMTPS | Stalwart (implicit TLS) | Stalwart |
| 587 | Submission | Stalwart (STARTTLS) | Stalwart |
| 993 | IMAPS | Stalwart (implicit TLS) | Stalwart |
| 995 | POP3S | Stalwart (implicit TLS) | Stalwart |
| 4190 | ManageSieve | Stalwart | Stalwart |
| 8000 | HTTP | Portainer Edge | Portainer |
| 9000 | HTTP | Portainer | Portainer |
| 9443 | HTTPS | Portainer | Portainer |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email server | Stalwart v0.16 | Single container, 1-2GB RAM, modern Rust-based, built-in JMAP/CalDAV/CardDAV, first-class Traefik docs |
| Hostname | `mail.perfectwork.app` | Consistent with us01's MAILCOW_HOSTNAME |
| cstation kind | `Container` (not Stack) | Single Docker image, no git repo to clone |
| Traefik routing | HTTP only | SMTP/IMAP protocols need direct TLS connections — not proxied |
| Stalwart HTTP | Port 8080 (internal, PW_NET) | Only reachable via Traefik, no host port binding |
| Stalwart TLS | Stalwart's own ACME | Simpler than cert-dumper sidecar, same Cloudflare API credentials, no dependency chain |
| ACME challenge | DNS-01 (Cloudflare) | Reuses CF_API_EMAIL/CF_API_KEY from config.yaml |
| Certificate domain | `mail.perfectwork.app` | Matches us01's existing MAILCOW_HOSTNAME |
| Migration tool | `imapsync` | Industry standard, handles Dovecot→Stalwart transparently |
| Container naming | `EU01_stalwart` | Follows `<HOST>_<service>` convention |
| Mail ports | Not through Traefik | Standard mail server practice; STARTTLS requires direct TLS |
| Firewall | Add 110/tcp, 4190/tcp | POP3 and ManageSieve not previously open |

## Domain Inventory (from us01)

| Domain | Mailboxes | Size | Priority |
|--------|-----------|------|----------|
| synercatalyst.com | 6 | 3.2 GB | Test domain |
| ansis.com.sg | 1 | 31 MB | 2nd |
| beautywithpro.com | 1 | 61 MB | 3rd |
| caryllynch.com | 1 | 330 MB | 4th |
| perfectwork.app | 4 | 121 MB | 5th |
| beyonique.com | 4 | 9.4 GB | 6th (largest) |
| postelsolutions.com | 1 | 3.8 MB | 7th (smallest) |

**Total: 18 mailboxes, ~13 GB**

### Mailbox list

```
synercatalyst.com:   adam.chang, info, kam-weng.goh, odoo, suseela.krishnan, wee-seng.loh
ansis.com.sg:        wee-seng.loh
beautywithpro.com:   info
beyonique.com:       account, andrea.loh, jeanne, wilson.loh
caryllynch.com:      email
perfectwork.app:     besolution, chris.cheong, kam-weng.goh, mail_service
postelsolutions.com: info
```

## Stalwart Fragment Schema

```yaml
# config/vps/eu01.synercatalyst.com/stalwart.yaml
apiVersion: cstation/v1
kind: Container
name: stalwart
enabled: true
image: stalwartlabs/stalwart:v0.16
container_name: EU01_stalwart
network: PW_NET
ports:
  - "25:25"       # SMTP
  - "110:110"     # POP3
  - "465:465"     # SMTPS
  - "587:587"     # Submission (STARTTLS)
  - "993:993"     # IMAPS
  - "995:995"     # POP3S
  - "4190:4190"   # ManageSieve
volumes:
  - /var/lib/stalwart/etc:/etc/stalwart
  - /var/lib/stalwart/data:/var/lib/stalwart
env:
  STALWART_RECOVERY_ADMIN: "admin:REPLACE_ME"
secrets:
  - CF_API_EMAIL
  - CF_API_KEY
restart_policy: unless-stopped
ulimits:
  nofile:
    soft: 65536
    hard: 65536
```

Key points:
- Port 8080 is NOT published to host — only reachable from Traefik via PW_NET
- `secrets` are resolved from `~/.config/cstation/config.yaml` at apply time (CF credentials for ACME)
- `STALWART_RECOVERY_ADMIN` must be changed after first login
- Stalwart runs as UID 2000 internally — directories must be `chown 2000:2000`

## Traefik Changes

### Removed from traefik.yaml

Ports removed from `ports` list:
- `"25:25"`, `"465:465"`, `"587:587"`, `"993:993"`, `"995:995"`

EntryPoints removed from `static_config.entryPoints`:
- `smtp`, `submissions`, `submission`, `imaps`, `pop3s`

### Added: Dynamic config for Stalwart HTTP routing

File: `/var/lib/traefik/conf/stalwart.yml` (written by StalwartService)

```yaml
http:
  routers:
    stalwart-admin:
      rule: "Host(`mail.perfectwork.app`)"
      entryPoints:
        - websecure
      service: stalwart-http
      tls:
        certResolver: le_dns_resolver
  services:
    stalwart-http:
      loadBalancer:
        serverPort: 8080
```

## StalwartService Implementation

### File: `src/cstation/commands/docker/services/stalwart.py`

```python
class StalwartService(ImageService):
    name = "stalwart"
    subdirs = ["etc", "data"]
```

Overrides:
- `_create_dirs()`: creates dirs + `chown 2000:2000`
- `_write_static_configs()`: writes Traefik dynamic config to `/var/lib/traefik/conf/stalwart.yml`
- `_plan_static_configs()`: checks if dynamic config exists and matches

### StalwartService behavior

1. `apply()` creates `/var/lib/stalwart/etc`, `/var/lib/stalwart/data`
2. `apply()` runs `chown -R 2000:2000 /var/lib/stalwart` (Stalwart UID)
3. `apply()` writes compose file with all volumes, ports, env, secrets
4. `apply()` writes `.env` with CF_API_EMAIL and CF_API_KEY (for ACME)
5. `apply()` writes `/var/lib/traefik/conf/stalwart.yml` (Traefik dynamic routing)
6. `apply()` runs `docker compose up -d`
7. On first start, Stalwart runs in bootstrap mode — admin credentials in `docker logs`

## Stalwart Post-Deploy Configuration

After `docker apply`, Stalwart must be configured via its web UI:

1. Access `http://localhost:8080/admin` via SSH tunnel
2. Complete setup wizard (5 steps)
3. Configure network listeners
4. Add domains and users
5. Configure TLS certificate (ACME DNS-01 with Cloudflare)
6. Generate DKIM keys per domain

This is manual configuration — not automated by cstation.

## TLS Architecture

```
Service   | Domain(s)              | ACME Resolver | Challenge    | Storage
----------|------------------------|---------------|--------------|---------------------------
Traefik   | *.synercatalyst.com    | le_dns_resolver | DNS-01 (CF) | /letsencrypt/acme_dns.json
Stalwart  | mail.perfectwork.app   | built-in ACME  | DNS-01 (CF) | /var/lib/stalwart/data
```

Both use the same Cloudflare API credentials (CF_API_EMAIL, CF_API_KEY).
No cert sharing. No sidecar containers. Each service manages its own cert lifecycle.

## Firewall Changes

Add to `config/vps/eu01.synercatalyst.com/vps.yaml` under `os.baseline.firewall.allow`:
- `110/tcp` (POP3)
- `4190/tcp` (ManageSieve)

Existing ports that remain:
- 22/tcp (SSH)
- 80/tcp, 443/tcp (HTTP/HTTPS — Traefik)
- 25/tcp, 465/tcp, 587/tcp (SMTP — Stalwart)
- 993/tcp, 995/tcp (IMAP/POP3S — Stalwart)
- 8000/tcp, 9000/tcp (Portainer)

## us01 Reference (for migration)

- Mailcow location: `/var/lib/mailcow/`
- Mailcow hostname: `mail.perfectwork.app`
- Mailcow HTTP_PORT=8088, HTTPS_PORT=8089 (via nginx-mailcow on PW_NET)
- Mailcow uses `mailcow_mailcow-network` bridge + PW_NET
- Container naming on us01: `mailcow-*` prefix
- Docker compose: `/var/lib/mailcow/docker-compose.yml` (686 lines, 21 containers)
- Mailcow admin: admin/moohoo (default)
- MySQL creds in `/var/lib/mailcow/mailcow.conf`: DBPASS, DBROOT
- Volumes: mysql-vol-1 (204MB), vmail-vol-1 (13GB), redis-vol-1, rspamd-vol-1, postfix-vol-1, crypt-vol-1, etc.