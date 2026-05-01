# Migration: us01 → us02 (Email)

**Source:** us01.synercatalyst.com (209.182.236.52:8288, Mailcow, 21 containers)
**Target:** us02.synercatalyst.com (152.53.169.95, Netcup ARM64, 6vCPU, 8GB RAM, 256GB disk)
**Services:** Stalwart Mail Server, Traefik, Portainer
**Email domains:** 7 domains, 18 mailboxes, ~13GB total
**Email server:** Stalwart v0.16 (replacing Mailcow on us01)
**Traefik routing:** HTTPS only (admin UI, JMAP). SMTP/IMAP bound directly by Stalwart.

---

## Prerequisites (DONE)

- [x] VPS baseline applied (all 13 phases)
- [x] Traefik deployed
- [x] Portainer deployed
- [x] Stalwart container deployed (bootstrap mode, port 8080 open)
- [x] All 7 mail ports open in UFW (25, 110, 465, 587, 993, 995, 4190)

---

## Phase D: Deploy Stalwart on us02 (email migration)

### D.1: Configure Stalwart (Setup Wizard)

> Stalwart is currently in bootstrap mode on us02. Port 8080 is open.
> SSH tunnel: `ssh -L 8080:localhost:8080 root@152.53.169.95`

- [ ] Open `http://localhost:8080/admin` via SSH tunnel
- [ ] Sign in with admin:REPLACE_ME (from `STALWART_RECOVERY_ADMIN` env var)
- [ ] Step 1: Set hostname=`mail.us02.synercatalyst.com`, Domain=`synercatalyst.com`, ACME=No, DKIM=Yes
- [ ] Step 2: Storage=RocksDB (default)
- [ ] Step 3: Directory=Internal (default)
- [ ] Step 4: Logging=Console (Docker logging)
- [ ] Step 5: DNS=Manual
- [ ] Save admin credentials
- [ ] `docker restart US02_stalwart`
- [ ] Verify: `ssh root@152.53.169.95 "docker logs US02_stalwart 2>&1 | tail -5"`
- [ ] Verify SMTP: `nc -z 152.53.169.95 25` (should succeed)
- [ ] Verify IMAP: `nc -z 152.53.169.95 993` (should succeed)

### D.2: Post-wizard Stalwart configuration

- [ ] Configure TLS certificate (ACME DNS-01 via Cloudflare, same `CF_API_EMAIL`/`CF_API_KEY`)
- [ ] Configure network listeners:
  - SMTP: port 25 (inbound)
  - Submission: port 587 (STARTTLS)
  - SMTPS: port 465 (implicit TLS)
  - IMAPS: port 993 (implicit TLS)
  - POP3S: port 995 (implicit TLS)
  - ManageSieve: port 4190
  - HTTP: port 8080 (admin/JMAP, proxied by Traefik)
- [ ] Set `useXForwarded = true` on HTTP listener (for Traefik proxy)
- [ ] Set `defaultHostname = mail.us02.synercatalyst.com`
- [ ] Add 7 domains: synercatalyst.com, ansis.com.sg, beautywithpro.com, beyonique.com, caryllynch.com, perfectwork.app, postelsolutions.com
- [ ] Create 18 user accounts (see domain inventory below)
- [ ] Generate DKIM keys per domain
- [ ] Record DKIM public keys for DNS setup

### D.3: Pre-migration DNS preparation (per domain)

> Lower TTLs to 300s on ALL domains before migration. Wait 24-48h for propagation.

Current DNS state:

| Domain | MX record | Points to | IP |
|--------|-----------|-----------|-----|
| synercatalyst.com | 0 mail.perfectwork.app | us01 | 209.182.236.52 |
| ansis.com.sg | 10 mail.ansis.com.sg | eu01 | 37.27.218.255 |
| beautywithpro.com | 10 mail.perfectwork.app | us01 | 209.182.236.52 |
| beyonique.com | 0 mail.perfectwork.app | us01 | 209.182.236.52 |
| caryllynch.com | 0 caryllynch.com | us01 | 209.182.236.52 |
| perfectwork.app | 0 mail.perfectwork.app | us01 | 209.182.236.52 |
| postelsolutions.com | 16 mail.perfectwork.app | us01 | 209.182.236.52 |

- [ ] Lower TTLs to 300s on all 7 domains (MX, SPF, DKIM, DMARC, A records)
- [ ] Wait 24-48h for TTL propagation
- [ ] Prepare new DNS records (don't activate yet):

**New DNS template (per domain):**
```
MX      @   mail.us02.synercatalyst.com  300
A       mail.us02.synercatalyst.com      152.53.169.95  300
TXT     @   v=spf1 mx a ip4:152.53.169.95 ~all  300
TXT     default._domainkey   <DKIM_PUBLIC_KEY>  300
TXT     _dmarc  v=DMARC1; p=none; rua=mailto:dmarc@<domain>  300
CNAME   autoconfig   mail.us02.synercatalyst.com  300
CNAME   autodiscover mail.us02.synercatalyst.com  300
```

### D.4: Migrate mailboxes with imapsync

> us01 Docker exec is broken (seccomp). Use imapsync from your local machine.

Migration order (smallest first):

| # | Domain | Mailboxes | Approx Size | ☐ |
|---|--------|-----------|-------------|-----|
| 1 | postelsolutions.com | info | 3.8 MB | ☐ |
| 2 | ansis.com.sg | wee-seng.loh | 31 MB | ☐ |
| 3 | beautywithpro.com | info | 61 MB | ☐ |
| 4 | caryllynch.com | email | 330 MB | ☐ |
| 5 | perfectwork.app | besolution, chris.cheong, kam-weng.goh, mail_service | 121 MB | ☐ |
| 6 | synercatalyst.com | adam.chang, info, kam-weng.goh, odoo, suseela.krishnan, wee-seng.loh | 3.2 GB | ☐ |
| 7 | beyonique.com | account, andrea.loh, jeanne, wilson.loh | 9.4 GB | ☐ |

For each mailbox:
```bash
imapsync --host1 209.182.236.52 --port1 993 --ssl1 \
  --user1 USER@DOMAIN --password1 'XXXX' \
  --host2 152.53.169.95 --port2 993 --ssl2 \
  --user2 USER@DOMAIN --password2 'XXXX'
```

- [ ] Install imapsync locally if needed: `brew install imapsync` (macOS)
- [ ] Test with postelsolutions.com (smallest domain)
- [ ] Migrate all 18 mailboxes
- [ ] Verify mailbox sizes match on us02

### D.5: DNS cutover (per domain)

> Cutover one domain at a time. Start with postelsolutions.com (smallest, test domain).

For each domain:
- [ ] Update MX record → `mail.us02.synercatalyst.com` (priority 10)
- [ ] Update/add A record `mail.us02.synercatalyst.com` → `152.53.169.95`
- [ ] Update SPF → `v=spf1 mx a ip4:152.53.169.95 ~all`
- [ ] Update DKIM → Stalwart-generated public key
- [ ] Update DMARC → `v=DMARC1; p=none; rua=mailto:dmarc@<domain>`
- [ ] Update autodiscover/autoconfig CNAMEs → `mail.us02.synercatalyst.com`
- [ ] Verify: send test email → arrives on us02
- [ ] Verify: reply from us02 → arrives at external provider

Cutover order:
1. [ ] postelsolutions.com (test domain)
2. [ ] ansis.com.sg (note: currently pointing to eu01!)
3. [ ] beautywithpro.com
4. [ ] caryllynch.com
5. [ ] perfectwork.app
6. [ ] synercatalyst.com
7. [ ] beyonique.com (largest, last)

### D.6: Post-migration verification

- [ ] Monitor us02: `ssh root@152.53.169.95 "docker logs US02_stalwart -f"`
- [ ] Full send/receive test for each domain
- [ ] Remove `STALWART_RECOVERY_ADMIN` env var in `US02_stalwart.yaml`
- [ ] Update DNS TTLs back to 3600+
- [ ] Keep us01 running 48-72h as fallback

### D.7: Cleanup

- [ ] Remove eu01 secrets from config.yaml (if eu01 Stalwart is no longer needed)
- [ ] Consider decommissioning us01 Mailcow after 72h
- [ ] Update this checklist — mark Phase D complete

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
| Email server | Stalwart v0.16 | Replaces Mailcow (21 containers → 1 container) |
| Hostname | mail.us02.synercatalyst.com | Server hostname for Stalwart |
| TLS for HTTPS | Traefik ACME (Cloudflare DNS-01) | Admin UI + JMAP |
| TLS for SMTP/IMAP | Stalwart's own ACME (Cloudflare DNS-01) | `mail.us02.synercatalyst.com` cert |
| Migration tool | imapsync | us01 Docker exec broken; imapsync works via IMAP |
| Test domain | postelsolutions.com | Smallest (3.8 MB, 1 mailbox) |

## Architecture

```
Browser ──HTTPS:443──► Traefik ──HTTP:8080──► Stalwart (admin UI / JMAP)
                          │
                     Traefik gets *.us02.synercatalyst.com
                     via Cloudflare DNS-01

Mail client ──TLS:465──► Stalwart (direct)
Mail client ──STARTTLS:587──► Stalwart (direct)
Mail client ──TLS:993──► Stalwart (direct)

                     Stalwart gets mail.us02.synercatalyst.com
                     via Cloudflare DNS-01 (same CF_API_EMAIL/KEY)
```

## us01 reference

- Location: `/var/lib/mailcow/` (21 containers)
- Hostname: `mail.perfectwork.app`
- HTTP: nginx-mailcow on PW_NET
- Ports: SMTP 25, SMTPS 465, Submission 587, IMAPS 993, POP3S 995
- Docker exec is broken (seccomp issue) — use imapsync for migration