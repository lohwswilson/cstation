# Implementation Plan: Email Migration Phase D (Stalwart on eu01)

## Objective

Deploy Stalwart Mail Server on eu01, configure it to receive email for 7 domains, migrate 18 mailboxes from us01 (Mailcow) via imapsync, and cut over DNS domain by domain.

## Prerequisites

- Phases A-C complete (eu01 baseline, Docker, Traefik, Portainer)
- Stalwart Docker image supports ARM64 (confirmed: `stalwartlabs/stalwart:v0.16`)
- Cloudflare API credentials in `~/.config/cstation/config.yaml` (already used by Traefik)

## Sub-phases

### D.1: Update cstation code ✅ COMPLETE

#### D.1a. Create StalwartService ✅

**Created**: `src/cstation/commands/docker/services/stalwart.py`

Implementation details:
- `StalwartService(ImageService)` with `name = "stalwart"`, `subdirs = ["etc", "data"]`
- `_write_static_configs()`: writes Traefik dynamic config to `/var/lib/traefik/conf/stalwart.yml`
  - Routes `Host(mail.perfectwork.app)` on `websecure` entrypoint → Stalwart:8080
  - Uses `le_dns_resolver` for TLS certificate
- `_plan_static_configs()`: checks if dynamic config matches desired state
- `apply()` override: calls `super().apply()` then `chown -R 2000:2000 /var/lib/stalwart` (Stalwart UID)
- `_STALWART_TRAEFIK_DYNAMIC_CONFIG` module-level constant for the dynamic config dict
- Registered via `register_service("stalwart", StalwartService)`

#### D.1b. Register StalwartService ✅

**Modified**: `src/cstation/commands/docker/services/__init__.py`

Added: `from .stalwart import StalwartService  # noqa: F401`

#### D.1c. Create Stalwart fragment ✅

**Created**: `config/vps/eu01.synercatalyst.com/stalwart.yaml`

```yaml
apiVersion: cstation/v1
kind: Container
name: stalwart
enabled: true
image: stalwartlabs/stalwart:v0.16
container_name: EU01_stalwart
network: PW_NET
ports:
  - "25:25"
  - "110:110"
  - "465:465"
  - "587:587"
  - "993:993"
  - "995:995"
  - "4190:4190"
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

Note: Port 8080 is NOT published to host — only reachable from Traefik via PW_NET.

#### D.1d. Modify Traefik fragment ✅

**Modified**: `config/vps/eu01.synercatalyst.com/traefik.yaml`

Removed from `ports`:
- `"25:25"`, `"465:465"`, `"587:587"`, `"993:993"`, `"995:995"`

Removed from `static_config.entryPoints`:
- `smtp` (port 25), `submissions` (port 465), `submission` (port 587), `imaps` (port 993), `pop3s` (port 995)

Traefik now only handles HTTP(S) traffic. SMTP/IMAP ports are bound directly by Stalwart.

#### D.1e. Delete Mailcow fragment ✅

**Deleted**: `config/vps/eu01.synercatalyst.com/mailcow.yaml`

(Replaced by stalwart.yaml.)

#### D.1f. Update VPS firewall ✅

**Modified**: `config/vps/eu01.synercatalyst.com/vps.yaml`

Added to `os.baseline.firewall.allow`:
- `110/tcp` (POP3)
- `4190/tcp` (ManageSieve)

#### D.1g. Add Stalwart secrets to config ✅

**Modified**: `~/.config/cstation/config.yaml`

Added under `vps.secrets.eu01.synercatalyst.com`:
```yaml
stalwart:
  CF_API_EMAIL: "syner.catalyst@gmail.com"
  CF_API_KEY: "923abedd02920ce74104a899309bec1434d0c"
```

(Same credentials used by Traefik — reused for Stalwart ACME DNS-01 challenge.)

#### D.1h. Write tests ✅

Added 10 tests to `tests/commands/test_docker_cli.py`:
- `test_stalwart_compose_includes_all_ports` — verifies all 7 ports in compose output
- `test_stalwart_compose_includes_env_and_secrets` — verifies env + env_file in compose
- `test_stalwart_create_dirs` — verifies /var/lib/stalwart, /etc, /data dirs
- `test_stalwart_static_config` — verifies plan checks for stalwart.yml
- `test_stalwart_apply_chown` — verifies chown 2000:2000 is called
- `test_stalwart_write_traefik_dynamic_config` — verifies dynamic config written to Traefik conf dir
- `test_stalwart_in_registry` — verifies "stalwart" in available_services
- `test_stalwart_dynamic_config_routes_to_8080` — verifies routing to port 8080 with le_dns_resolver
- `test_docker_plan_stalwart` — CLI plan test for stalwart service
- `test_docker_apply_stalwart` — CLI apply test for stalwart service

#### D.1i. Verify ✅

All 94 tests pass (53 VPS + 41 Docker).

---

### D.2: Re-deploy Traefik (remove mail ports) ✅ COMPLETE

- [x] `uv run cstation vps apply eu01.synercatalyst.com --phase firewall` — added 110/tcp, 4190/tcp
- [x] `uv run cstation docker plan eu01.synercatalyst.com --service traefik` — verified changes
- [x] `uv run cstation docker apply eu01.synercatalyst.com --service traefik --yes`
- [x] Verify: Traefik running with only ports 80, 443
- [x] Verify: `curl -s -o /dev/null -w "%{http_code}" http://37.27.218.255` → 301

---

### D.3: Deploy Stalwart on eu01 ✅ COMPLETE

- [x] `uv run cstation docker plan eu01.synercatalyst.com --service stalwart` — reviewed plan
- [x] `uv run cstation docker apply eu01.synercatalyst.com --service stalwart --yes`
- [x] Verified: EU01_stalwart running (healthy), ports 25, 110, 465, 587, 993, 995, 4190 bound
- [x] Bootstrap mode active: port 8080 open for initial setup
- [x] Fixed: Traefik dynamic config `serverPort` → `servers` with `url` (Traefik v3 file provider format)
- [x] Fixed: Traefik .env had `REPLACE_ME` → re-applied with real secrets from config.yaml
- [x] Re-applied Stalwart and Portainer dynamic configs with fixed format
- [x] Restarted Traefik — no more config errors
- [x] Verified: TLS cert auto-provisioned for `mail.ansis.com.sg` via Cloudflare DNS-01
- [x] Verified: `https://mail.ansis.com.sg/admin` → 200 OK (Stalwart admin UI accessible via Traefik)

- [x] `uv run cstation docker plan eu01.synercatalyst.com --service stalwart` — reviewed plan
- [x] `uv run cstation docker apply eu01.synercatalyst.com --service stalwart --yes`
- [x] Verify: EU01_stalwart running (healthy), ports 25, 110, 465, 587, 993, 995, 4190 bound
- [x] Bootstrap mode active: port 8080 open for initial setup
- [x] Also updated: stalwart.yaml now routes both mail.perfectwork.app and mail.ansis.com.sg via Traefik

---

### D.4: Configure Stalwart (Setup Wizard) ✅ COMPLETE

**Access:** `https://mail.ansis.com.sg/admin` (TLS cert auto-provisioned via Cloudflare DNS-01)

**Wizard steps completed:**
- Step 1: Hostname=`mail.ansis.com.sg`, Domain=`synercatalyst.com`, ACME=No (configure later), DKIM=Yes
- Step 2: Storage=RocksDB (default)
- Step 3: Directory=Internal (default)
- Step 4: Logging=Console (for Docker)
- Step 5: DNS=Manual

**Verified:**
- SMTP `220 mail.ansis.com.sg Stalwart ESMTP` ✅
- Admin UI `https://mail.ansis.com.sg/admin/` → 200 ✅

---

### D.5: Post-wizard Stalwart configuration

After the wizard, sign in at `https://mail.perfectwork.app/admin` (via Traefik) or `http://localhost:8080/admin` (via tunnel).

**TLS Certificate:**
- [ ] Navigate to Settings → TLS → Certificates
- [ ] Add certificate: Type = ACME, Provider = Cloudflare DNS-01
- [ ] Set CF_API_EMAIL and CF_API_KEY (from env vars already in .env)
- [ ] Request certificate for `mail.perfectwork.app`
- [ ] Wait for cert to be issued

**Network Listeners:**
- [ ] Navigate to Settings → Network → Listeners
- [ ] Verify: SMTP (25), Submission/STARTTLS (587), SMTPS (465), IMAPS (993), POP3S (995), ManageSieve (4190)
- [ ] HTTP listener (8080) — verify `useXForwarded = true` for Traefik proxy
- [ ] Verify `defaultHostname = mail.perfectwork.app`

**Domains:**
- [ ] Add domain: `synercatalyst.com` (default, from wizard)
- [ ] Add domain: `ansis.com.sg`
- [ ] Add domain: `beautywithpro.com`
- [ ] Add domain: `beyonique.com`
- [ ] Add domain: `caryllynch.com`
- [ ] Add domain: `perfectwork.app`
- [ ] Add domain: `postelsolutions.com`

**Users (create each mailbox):**
- [ ] `adam.chang@synercatalyst.com`
- [ ] `info@synercatalyst.com`
- [ ] `kam-weng.goh@synercatalyst.com`
- [ ] `odoo@synercatalyst.com`
- [ ] `suseela.krishnan@synercatalyst.com`
- [ ] `wee-seng.loh@synercatalyst.com`
- [ ] `wee-seng.loh@ansis.com.sg`
- [ ] `info@beautywithpro.com`
- [ ] `account@beyonique.com`
- [ ] `andrea.loh@beyonique.com`
- [ ] `jeanne@beyonique.com`
- [ ] `wilson.loh@beyonique.com`
- [ ] `email@caryllynch.com`
- [ ] `besolution@perfectwork.app`
- [ ] `chris.cheong@perfectwork.app`
- [ ] `kam-weng.goh@perfectwork.app`
- [ ] `mail_service@perfectwork.app`
- [ ] `info@postelsolutions.com`

**DKIM Keys:**
- [ ] Generate DKIM key for each domain
- [ ] Record the public keys for DNS setup (Phase D.8)

**Security hardening:**
- [ ] Remove `STALWART_RECOVERY_ADMIN` from stalwart.yaml
- [ ] Re-apply: `uv run cstation docker apply eu01.synercatalyst.com --service stalwart --yes`
- [ ] Verify admin login works with permanent credentials only

---

### D.6: Pre-migration DNS preparation (per domain)

For each domain (start with `synercatalyst.com`):

- [ ] Document current DNS records from us01:

```bash
# From local machine, for each domain:
dig MX synercatalyst.com +short
dig A mail.perfectwork.app +short
dig TXT synercatalyst.com +short           # SPF
dig TXT _dmarc.synercatalyst.com +short     # DMARC
dig TXT default._domainkey.synercatalyst.com +short  # DKIM
dig CNAME autodiscover.synercatalyst.com +short
dig CNAME autoconfig.synercatalyst.com +short
```

- [ ] Lower TTL to 300s on all MX, SPF, DKIM, DMARC, A records (via Cloudflare dashboard)
- [ ] Wait 24-48h for TTL propagation
- [ ] Create (but do NOT activate) DNS records pointing to eu01:
  - `mail.perfectwork.app` A record → `37.27.218.255` (if not already)
  - MX → `mail.perfectwork.app` (priority 10)
  - SPF → `v=spf1 mx a ip4:37.27.218.255 ~all`
  - DKIM → Stalwart-generated key (from D.5)
  - DMARC → `v=DMARC1; p=none; rua=mailto:dmarc@<domain>`
  - autodiscover CNAME → `mail.perfectwork.app`
  - autoconfig CNAME → `mail.perfectwork.app`

---

### D.7: Migrate mailboxes with imapsync

**Install imapsync** on local machine:
```bash
# macOS
brew install imapsync

# Ubuntu
sudo apt install imapsync
```

**Migration order** (smallest first for testing):

| # | Domain | Mailboxes | Size | Status |
|---|--------|-----------|------|--------|
| 1 | postelsolutions.com | 1 | 3.8 MB | ☐ |
| 2 | ansis.com.sg | 1 | 31 MB | ☐ |
| 3 | beautywithpro.com | 1 | 61 MB | ☐ |
| 4 | caryllynch.com | 1 | 330 MB | ☐ |
| 5 | perfectwork.app | 4 | 121 MB | ☐ |
| 6 | synercatalyst.com | 6 | 3.2 GB | ☐ |
| 7 | beyonique.com | 4 | 9.4 GB | ☐ |

**For each mailbox:**

```bash
# Dry run first
imapsync --dry \
  --host1 us01.synercatalyst.com --port1 993 --ssl1 \
  --user1 user@domain.com --password1 'XXXX' \
  --host2 37.27.218.255 --port2 993 --ssl2 \
  --user2 user@domain.com --password2 'XXXX'

# Full sync
imapsync \
  --host1 us01.synercatalyst.com --port1 993 --ssl1 \
  --user1 user@domain.com --password1 'XXXX' \
  --host2 37.27.218.255 --port2 993 --ssl2 \
  --user2 user@domain.com --password2 'XXXX'
```

**Note**: Passwords for us01 accounts must be obtained from the Mailcow admin UI on us01 (`https://us01.synercatalyst.com:8089`). Passwords for eu01 accounts are set during D.5 user creation.

**Post-sync verification per mailbox:**
- [ ] Folder count matches
- [ ] Message count matches
- [ ] Recent messages present
- [ ] Flags (read/unread) preserved

---

### D.8: DNS cutover (per domain)

**After mailbox sync completes for a domain:**

- [ ] Update MX record → `mail.perfectwork.app` (pointing to `37.27.218.255`)
- [ ] Update SPF TXT record → `v=spf1 mx a ip4:37.27.218.255 ~all`
- [ ] Update DKIM TXT record → Stalwart-generated public key
- [ ] Update DMARC TXT record
- [ ] Update autodiscover CNAME → `mail.perfectwork.app`
- [ ] Update autoconfig CNAME → `mail.perfectwork.app`
- [ ] Verify: `dig MX <domain>` → returns eu01
- [ ] Test: send email from external provider → arrives on eu01
- [ ] Test: reply from eu01 mailbox → arrives at external provider
- [ ] Test: IMAP client connects to `mail.perfectwork.host` on port 993

**Repeat for each domain in migration order.**

---

### D.9: Post-migration

- [ ] Keep us01 running for 48-72h as fallback (accepts queued mail)
- [ ] Monitor eu01: `ssh root@37.27.218.255 "docker logs EU01_stalwart -f"`
- [ ] Full verification: external send → reply → IMAP from multiple clients
- [ ] Verify all 7 domains accepting and sending email
- [ ] Update DNS TTLs back to 3600+
- [ ] Remove `STALWART_RECOVERY_ADMIN` from stalwart.yaml env if not already done
- [ ] Disable Stalwart HTTP listener on port 8080 after admin initial setup (admin accessible via Traefik only)
- [ ] Update `docs/migration/us01-to-eu01.md` — mark Phase D complete
- [ ] Eventually decommission us01 (Phase H)

---

## Files Changed (Summary)

### New files ✅
- `config/vps/eu01.synercatalyst.com/stalwart.yaml` — Stalwart Container fragment
- `src/cstation/commands/docker/services/stalwart.py` — StalwartService class
- `docs/superpowers/specs/2026-04-30-email-migration-stalwart-design.md` — Design spec
- `docs/superpowers/plans/2026-04-30-email-migration-phase-d.md` — This plan

### Modified files ✅
- `config/vps/eu01.synercatalyst.com/traefik.yaml` — removed SMTP/IMAP ports and entrypoints
- `config/vps/eu01.synercatalyst.com/vps.yaml` — added 110/tcp, 4190/tcp to firewall
- `src/cstation/commands/docker/services/__init__.py` — added StalwartService import
- `~/.config/cstation/config.yaml` — added stalwart secrets (CF_API_EMAIL, CF_API_KEY)
- `tests/commands/test_docker_cli.py` — added 10 Stalwart tests
- `docs/migration/us01-to-eu01.md` — updated Phase D with Stalwart details

### Deleted files ✅
- `config/vps/eu01.synercatalyst.com/mailcow.yaml` — replaced by stalwart.yaml