# Migration: us01 → eu01 (Email)

**Source:** us01.synercatalyst.com (209.182.236.52:8288, still serving traffic)
**Target:** eu01.synercatalyst.com (37.27.218.255, Hetzner HEL1, ARM64, 4vCPU, 8GB RAM, 76GB disk)
**Services:** Stalwart Mail Server, Traefik, Portainer
**Email domains:** 7 domains, 18 mailboxes, ~13GB total
**Email server:** Stalwart v0.16 (replacing Mailcow on us01)
**Traefik routing:** HTTPS only (admin UI, JMAP). SMTP/IMAP bound directly by Stalwart.

---

## Phase A: Prepare eu01 via cstation vps ✅ COMPLETE

- [x] All 6 baseline phases applied and verified

## Phase B: System optimization + Docker + Hostname ✅ COMPLETE

- [x] All 7 optimization phases (7-13) applied and verified
- [x] Idempotent re-apply confirmed

## Phase C: Deploy Traefik + Portainer on eu01 ✅ COMPLETE

- [x] Traefik deployed via `cstation docker apply`
- [x] Portainer deployed via `cstation docker apply`
- [x] Cloudflare secrets written from config.yaml
- [x] HTTPS redirect verified (301)
- [x] Traefik dashboard accessible via SSH tunnel

## Phase D: Deploy Stalwart on eu01 (email migration)

> Replaces Mailcow (21 containers, 4GB+ RAM) with Stalwart (single container, 1-2GB RAM).
> Detailed spec: `docs/superpowers/specs/2026-04-30-email-migration-stalwart-design.md`
> Detailed plan: `docs/superpowers/plans/2026-04-30-email-migration-phase-d.md`

### D.1: Update cstation code
- [ ] Create `src/cstation/commands/docker/services/stalwart.py` (StalwartService)
- [ ] Add StalwartService import to `__init__.py`
- [ ] Create `config/vps/eu01.synercatalyst.com/stalwart.yaml`
- [ ] Modify `config/vps/eu01.synercatalyst.com/traefik.yaml` — remove SMTP/IMAP ports, remove entrypoints
- [ ] Delete `config/vps/eu01.synercatalyst.com/mailcow.yaml`
- [ ] Modify `config/vps/eu01.synercatalyst.com/vps.yaml` — add 110/tcp, 4190/tcp to firewall
- [ ] Add stalwart secrets to `~/.config/cstation/config.yaml`
- [ ] Write tests for StalwartService
- [ ] `uv run pytest -q` — all tests pass

### D.2: Re-deploy Traefik (remove mail ports)
- [ ] `uv run cstation vps apply eu01.synercatalyst.com --phase firewall` — add ports
- [ ] `uv run cstation docker plan eu01.synercatalyst.com --service traefik` — verify
- [ ] `uv run cstation docker apply eu01.synercatalyst.com --service traefik --yes`
- [ ] Verify: Traefik running with HTTP ports only (80, 443, 8000, 9000, 9443)

### D.3: Deploy Stalwart on eu01
- [ ] `uv run cstation docker plan eu01.synercatalyst.com --service stalwart`
- [ ] `uv run cstation docker apply eu01.synercatalyst.com --service stalwart --yes`
- [ ] Verify: `docker ps | grep stalwart` — running
- [ ] Verify: Stalwart listening on ports 25, 465, 587, 993, 995, 110, 4190
- [ ] Get bootstrap credentials from docker logs

### D.4: Configure Stalwart (Setup Wizard)
- [ ] SSH tunnel: `ssh -L 8080:localhost:8080 root@37.27.218.255`
- [ ] Open `http://localhost:8080/admin`
- [ ] Step 1: Hostname=`mail.perfectwork.app`, Domain=`synercatalyst.com`, ACME=No (configure later), DKIM=Yes
- [ ] Step 2: Storage=RocksDB (default)
- [ ] Step 3: Directory=Internal (default)
- [ ] Step 4: Logging=Console (Docker)
- [ ] Step 5: DNS=Manual
- [ ] Save admin credentials
- [ ] `docker restart EU01_stalwart`

### D.5: Post-wizard Stalwart configuration
- [ ] Configure TLS certificate (ACME DNS-01 via Cloudflare)
- [ ] Configure network listeners (SMTP, Submission, SMTPS, IMAPS, POP3S, ManageSieve, HTTP)
- [ ] Set `useXForwarded = true` on HTTP listener
- [ ] Set `defaultHostname = mail.perfectwork.app`
- [ ] Add 7 domains: synercatalyst.com, ansis.com.sg, beautywithpro.com, beyonique.com, caryllynch.com, perfectwork.app, postelsolutions.com
- [ ] Create 18 user accounts (see domain inventory below)
- [ ] Generate DKIM keys per domain
- [ ] Record DKIM public keys for DNS setup

### D.6: Pre-migration DNS preparation (per domain)
- [ ] Document current DNS records from us01
- [ ] Lower TTLs to 300s (MX, SPF, DKIM, DMARC, A records)
- [ ] Wait 24-48h for TTL propagation
- [ ] Prepare new DNS records (don't activate yet)

### D.7: Migrate mailboxes with imapsync
Migration order (smallest first):

| # | Domain | Mailboxes | Size | Status |
|---|--------|-----------|------|--------|
| 1 | postelsolutions.com | 1 | 3.8 MB | ☐ |
| 2 | ansis.com.sg | 1 | 31 MB | ☐ |
| 3 | beautywithpro.com | 1 | 61 MB | ☐ |
| 4 | caryllynch.com | 1 | 330 MB | ☐ |
| 5 | perfectwork.app | 4 | 121 MB | ☐ |
| 6 | synercatalyst.com | 6 | 3.2 GB | ☐ |
| 7 | beyonique.com | 4 | 9.4 GB | ☐ |

For each mailbox:
```bash
imapsync --host1 us01.synercatalyst.com --port1 993 --ssl1 \
  --user1 USER@DOMAIN --password1 'XXXX' \
  --host2 37.27.218.255 --port2 993 --ssl2 \
  --user2 USER@DOMAIN --password2 'XXXX'
```

### D.8: DNS cutover (per domain)
- [ ] Update MX → mail.perfectwork.app (37.27.218.255)
- [ ] Update SPF → `v=spf1 mx a ip4:37.27.218.255 ~all`
- [ ] Update DKIM → Stalwart-generated public key
- [ ] Update DMARC → `v=DMARC1; p=none; rua=mailto:dmarc@<domain>`
- [ ] Update autodiscover/autoconfig CNAMEs → mail.perfectwork.app
- [ ] Verify: email flow for each domain

### D.9: Post-migration
- [ ] Keep us01 running 48-72h as fallback
- [ ] Monitor eu01: `docker logs EU01_stalwart -f`
- [ ] Full verification: send/receive/IMAP from multiple clients
- [ ] Remove `STALWART_RECOVERY_ADMIN` env var
- [ ] Update DNS TTLs to 3600+
- [ ] Update this checklist — mark Phase D complete

## Phase E-G: Remaining (will be detailed after Phase D)

- Phase E: Pre-migration DNS preparation (covered in D.6)
- Phase F: Migrate email data (covered in D.7)
- Phase G: DNS cutover (covered in D.8)

## Phase H: Post-migration
- [ ] Keep us01 running for 48-72h
- [ ] Full email verification cycle
- [ ] Configure Portainer Edge endpoints (other VPSes → eu01)
- [ ] Update DNS TTLs back to normal
- [ ] Decommission us01

---

## Domain inventory (from us01 Mailcow)

| Domain | Mailboxes | Size |
|--------|-----------|------|
| synercatalyst.com | adam.chang, info, kam-weng.goh, odoo, suseela.krishnan, wee-seng.loh | 3.2 GB |
| ansis.com.sg | wee-seng.loh | 31 MB |
| beautywithpro.com | info | 61 MB |
| beyonique.com | account, andrea.loh, jeanne, wilson.loh | 9.4 GB |
| caryllynch.com | email | 330 MB |
| perfectwork.app | besolution, chris.cheong, kam-weng.goh, mail_service | 121 MB |
| postelsolutions.com | info | 3.8 MB |

**Total: 18 mailboxes, ~13 GB**

## Key decisions

| Decision | Choice | Notes |
|----------|--------|-------|
| Email server | Stalwart v0.16 | Replaces Mailcow (21 containers → 1 container, 4GB+ → 1-2GB RAM) |
| Hostname | mail.perfectwork.app | Consistent with us01's MAILCOW_HOSTNAME |
| TLS for HTTPS | Traefik ACME (Cloudflare DNS-01) | `*.synercatalyst.com` wildcard for admin UI |
| TLS for SMTP/IMAP | Stalwart's own ACME (Cloudflare DNS-01) | `mail.perfectwork.app` cert, same CF credentials |
| Traefik HTTP routing | Dynamic config file | `/var/lib/traefik/conf/stalwart.yml` — auto-watched |
| SMTP/IMAP routing | Direct to Stalwart (no Traefik) | Standard email practice; STARTTLS needs direct TLS |
| cert-dumper | Not needed | Stalwart handles own certs via ACME DNS-01 |
| Migration tool | imapsync | Handles Dovecot→Stalwart transparently via IMAP protocol |
| cstation kind | Container (not Stack) | Single Docker image, no git repo |
| Container naming | EU01_stalwart | Follows `<HOST>_<service>` convention |
| Test domain | postelsolutions.com | Smallest (3.8 MB, 1 mailbox) |

## Architecture

```
Browser ──HTTPS:443──► Traefik ──HTTP:8080──► Stalwart (admin UI / JMAP)
                         │
                    Traefik gets *.synercatalyst.com
                    via Cloudflare DNS-01

Mail client ──TLS:465──► Stalwart (direct)
Mail client ──STARTTLS:587──► Stalwart (direct)
Mail client ──TLS:993──► Stalwart (direct)

                    Stalwart gets mail.perfectwork.app
                    via Cloudflare DNS-01 (same CF_API_EMAIL/KEY)
```

## us01 reference

- Location: `/var/lib/mailcow/` (21 containers)
- Hostname: `mail.perfectwork.app`
- HTTP: nginx-mailcow on PW_NET (port 8088/8089, behind us01 Traefik)
- Ports: SMTP 25, SMTPS 465, Submission 587, IMAPS 993, POP3S 995 (bound to host)
- MySQL creds in `/var/lib/mailcow/mailcow.conf`
- Docker exec broken on us01 (seccomp issue) — use `imapsync` for migration