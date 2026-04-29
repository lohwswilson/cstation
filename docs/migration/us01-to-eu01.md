# Migration: us01 → eu01 (Mailcow Email)

**Source:** us01.synercatalyst.com (still serving traffic)  
**Target:** eu01.synercatalyst.com (37.27.218.255, Hetzner HEL1, ARM64, 4vCPU, 8GB RAM, 76GB disk)  
**Services:** Mailcow email, Traefik, Portainer  
**Email domains:** 4-10 domains  
**Traefik routing:** All traffic (including Mailcow) through Traefik

---

## Phase A: Prepare eu01 via cstation vps

- [x] Edit `config/vps/eu01.synercatalyst.com.yaml` — verify firewall ports include: 22, 80, 443, 25, 465, 587, 993, 995
- [x] Edit `config/vps/eu01.synercatalyst.com.yaml` — verify `os.baseline` has: `upgrade_all: true`, `shell: zsh`, `terminal: xterm-256color`
- [x] `uv run cstation vps plan config/vps/eu01.synercatalyst.com.yaml`
- [x] Review plan output — confirm all 6 phases look correct
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml`
- [x] Verify: `ssh root@37.27.218.255 "ufw status"` — active with all 8 ports (22, 80, 443, 25, 465, 587, 993, 995)
- [x] Verify: `ssh root@37.27.218.255 "grep PasswordAuthentication /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf"` — `no`
- [x] Verify: `ssh root@37.27.218.255 "dpkg -s fail2ban docker.io containerd zsh | grep Status"` — all `install ok installed`
- [x] Verify: `ssh root@37.27.218.255 "echo $SHELL && echo $TERM"` — `/usr/bin/zsh` and `xterm-256color`

## Phase B: System optimization + Docker + Hostname (via `cstation vps apply`)

All Phase B settings are now declarative in `config/vps/eu01.synercatalyst.com.yaml` and applied via `cstation vps apply` (phases 7-13).

> The YAML now includes: `os.baseline.swap`, `os.baseline.tuning`, `os.baseline.fail2ban`, `os.hostname`, `os.journald`, `docker.daemon`, `docker.networks`, `docker.directories`.
>
> Previously these were manual SSH steps. They are now CLI phases.

### Plan first
- [x] `uv run cstation vps plan config/vps/eu01.synercatalyst.com.yaml` — review phases 7-13

### Apply all Phase B changes
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --yes`

### Or apply individual phases
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase swap`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase tuning`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase fail2ban`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase hostname`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase docker_daemon`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase docker_networks`
- [x] `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --phase docker_directories`

### Verification
- [x] Swap: `ssh root@37.27.218.255 "swapon --show && sysctl vm.swappiness"` — 4G swap, swappiness=10
- [x] Sysctl: `ssh root@37.27.218.255 "sysctl vm.swappiness vm.overcommit_memory net.ipv4.tcp_max_syn_backlog fs.inotify.max_user_watches net.ipv4.tcp_keepalive_time"` — 10, 1, 1024, 524288, 600
- [x] Journald: `ssh root@37.27.218.255 "cat /etc/systemd/journald.conf.d/99-cstation.conf"` — SystemMaxUse=500M, ForwardToSyslog=no
- [x] Fail2ban: `ssh root@37.27.218.255 "fail2ban-client status sshd"` — jail active
- [x] Hostname: `ssh root@37.27.218.255 "hostname"` — eu01.synercatalyst.com
- [x] Docker daemon: `ssh root@37.27.218.255 "cat /etc/docker/daemon.json && docker compose version"` — daemon.json correct, Compose v2.40.3
- [x] Docker networks: `ssh root@37.27.218.255 "docker network ls | grep PW_NET"` — present
- [x] Directories: `ssh root@37.27.218.255 "ls -ld /var/lib/perfectwork"` — exists
- [x] Idempotency: `uv run cstation vps apply config/vps/eu01.synercatalyst.com.yaml --yes` — re-apply shows all phases already configured

## Phase C: Deploy Traefik on eu01

- [ ] Create Traefik config directory: `ssh root@37.27.218.255 "mkdir -p /var/lib/traefik/eu01/{letsencrypt,conf,logs,etc}"`
- [ ] Write Traefik static config (`/var/lib/traefik/eu01/etc/traefik.yml`) with entrypoints: `web` (80), `websecure` (443), `smtp` (25), `submissions` (465), `submission` (587), `imaps` (993), `pop3s` (995)
- [ ] Write Traefik static config — enable Lets Encrypt (ACME) with `le_resolver`, Docker provider, and file provider watching `/var/lib/traefik/eu01/conf/`
- [ ] Deploy Traefik container on PW_NET with Docker socket mounted read-only
- [ ] Verify API: `ssh root@37.27.218.255 "curl -s http://localhost:8080/api/rawdata"` — should return JSON
- [ ] Verify HTTPS: `curl -s https://37.27.218.255` — should hit Traefik (404 or default backend)

## Phase D: Deploy Mailcow on eu01 (routed through Traefik)

- [ ] Clone: `ssh root@37.27.218.255 "git clone https://github.com/mailcow/mailcow-dockerized /opt/mailcow"`
- [ ] Generate config: `ssh root@37.27.218.255 "cd /opt/mailcow && ./generate_config.sh"`
- [ ] Edit `mailcow.conf` — set `SKIP_LETS_ENCRYPT=y`, `SKIP_NGINX=y`, `HTTP_PORT=8082`, `HTTPS_PORT=8443`
- [ ] Configure Mailcow to use PW_NET network
- [ ] Write Traefik dynamic config for Mailcow HTTP routes: admin UI + SOGo → internal port 8082/8443
- [ ] Write Traefik dynamic config for Mailcow TCP routes: 25/465/587 → Postfix, 993/995 → Dovecot
- [ ] Start Mailcow: `ssh root@37.27.218.255 "cd /opt/mailcow && docker compose up -d"`
- [ ] Verify: `ssh root@37.27.218.255 "cd /opt/mailcow && docker compose ps"` — all containers healthy
- [ ] Verify: access Mailcow admin UI via browser at `https://mail.<domain>.com`

## Phase E: Pre-migration DNS preparation (on us01)

- [ ] Document all DNS records for migration: MX, SPF, DKIM, DMARC, SRV, autodiscover/autoconfig CNAMEs
- [ ] Lower TTL on all MX/SPF/DKIM/DMARC/A records to 300s
- [ ] Wait 24-48 hours for TTL propagation
- [ ] Optionally test with a single non-critical domain first on eu01

## Phase F: Migrate email data (us01 → eu01)

- [ ] On us01: set Postfix to hold queue or stop Mailcow (`docker compose stop`)
- [ ] On us01: run Mailcow backup: `cd /opt/mailcow && ./helper-scripts/backup.sh`
- [ ] Transfer backup to eu01: `rsync -avz --progress /opt/mailcow/backup/ root@37.27.218.255:/opt/mailcow/backup/`
- [ ] On eu01: restore Mailcow data: `cd /opt/mailcow && ./helper-scripts/restore.sh`
- [ ] On eu01: restart Mailcow: `docker compose restart`
- [ ] Verify: mailboxes accessible, filters/rules intact, contacts/calendars present
- [ ] Verify: send test email to a migrated address from an external provider → arrives on eu01

## Phase G: DNS cutover

- [ ] Update MX records → eu01 IP (37.27.218.255)
- [ ] Update SPF records → include eu01 IP
- [ ] Copy/re-generate DKIM keys on eu01, update DNS TXT records
- [ ] Update autodiscover/autoconfig CNAMEs → eu01
- [ ] Verify: `dig MX <domain>.com` returns eu01
- [ ] Verify: send test email from external provider → arrives on eu01
- [ ] Verify: reply from eu01 mailbox → arrives at external provider
- [ ] Verify: IMAP client (Thunderbird/Outlook) connects successfully to eu01

## Phase H: Post-migration

- [ ] Keep us01 running for 48-72 hours as fallback (accepts any queued mail)
- [ ] Monitor eu01 mail logs: `ssh root@37.27.218.255 "cd /opt/mailcow && docker compose logs -f postfix-mailcow dovecot-mailcow"`
- [ ] Full verification cycle: external send → reply → IMAP from multiple clients
- [ ] Deploy Portainer agent: `docker run -d --name portainer_agent --network PW_NET -p 127.0.0.1:9001:9001 ...`
- [ ] Once confident: update DNS TTLs back to normal (3600+)
- [ ] Decommission us01

---

## Key decisions

| Decision | Choice | Notes |
|---|---|---|
| Traefik + Mailcow | Route through Traefik | Unified SSL, single entry point |
| Mailcow ACME | Disabled (`SKIP_LETS_ENCRYPT=y`) | Traefik handles all SSL |
| Mailcow nginx | Disabled (`SKIP_NGINX=y`) | Traefik proxies HTTP to Mailcow internal ports |
| Package versioning | No pins | `apt-get install` gets latest from repos |
| Swap | 4GB | Mailcow (ClamAV) is memory-hungry |
| Swappiness | 10 | Avoid swapping ClamAV prematurely on 8GB RAM |
| Docker log rotation | 10m × 3 files | Prevents disk fill on 76GB disk |
| Docker live-restore | true | Containers stay running during Docker daemon restart |
| Docker iptables | true | Docker manages iptables for container port mapping |
| Docker ulimits | nofile 65536 | Mailcow needs many open file descriptors |
| Kernel tuning | swappiness=10, overcommit=1, syn_backlog=1024, inotify=524288, keepalive=600 | Optimized for Docker + mail server |
| Journald | SystemMaxUse=500M, ForwardToSyslog=no | Cap journal size on 76GB disk |
| fail2ban bantime | 1h | Reasonable hardening for SSH brute-force protection |
| Hostname | eu01.synercatalyst.com | Declarative via `os.hostname` in YAML |
| Timezone | UTC | Standard server practice |
| Disk resize | Not now | 71GB free, monitor usage |

## Traefik config reference

Static config entrypoints:
```yaml
entryPoints:
  web: ":80"
  websecure: ":443"
  smtp: ":25"
  submissions: ":465"
  submission: ":587"
  imaps: ":993"
  pop3s: ":995"
```

Dynamic config TCP routers for Mailcow:
```yaml
tcp:
  routers:
    smtp:
      entryPoints: ["smtp"]
      service: mailcow-postfix
      rule: "HostSNI(`*`)"
    submissions:
      entryPoints: ["submissions"]
      service: mailcow-postfix-ssl
      rule: "HostSNI(`*`)"
    imaps:
      entryPoints: ["imaps"]
      service: mailcow-dovecot
      rule: "HostSNI(`*`)"
  services:
    mailcow-postfix:
      loadBalancer:
        servers:
          - address: "postfix-mailcow:25"
    mailcow-dovecot:
      loadBalancer:
        servers:
          - address: "dovecot-mailcow:993"
```