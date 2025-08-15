# Portainer Setup Guide with eu01.yml Host Variables

This guide demonstrates how the **Portainer profile** (`portainer.yml`) works with host-specific variables defined in `eu01.yml`.

## Overview

The setup consists of:
- **Profile**: `etc/ansible/profiles/portainer.yml` - Defines the Portainer deployment template
- **Host Variables**: `etc/ansible/host_vars/eu01.yml` - Contains server-specific configuration
- **Variable Override System**: Host variables automatically override profile defaults

## File Structure

```
cstation/
├── etc/ansible/
│   ├── profiles/
│   │   └── portainer.yml          # Portainer profile template
│   └── host_vars/
│       └── eu01.yml               # Host-specific variables
└── commands/server/setup/
    └── main.py                    # CLI implementation
```

## Configuration Details

### 1. Profile Template (portainer.yml)

The profile defines the basic Portainer deployment structure:

```yaml
# Basic container configuration
containers:
  portainer:
    name: "portainer"
    image: "portainer/portainer-ce:latest"
    ports:
      - "9000:9000"
      - "9443:9443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
      - "{{ portainer_data_path }}:/data"
    environment:
      PORTAINER_ADMIN_PASSWORD: "{{ portainer_admin_password }}"
      PORTAINER_DOMAIN: "{{ portainer_domain }}"
      PORTAINER_SSL_ENABLED: "{{ portainer_ssl_enabled }}"
    networks:
      - "{{ portainer_network.name }}"

# Default variables (can be overridden)
vars:
  domain_name: "portainer.localhost"
  ssl_email: "admin@localhost"
  ssl_enabled: false
  portainer_admin_password: "admin123"
  portainer_domain: "{{ domain_name }}"
  portainer_ssl_enabled: "{{ ssl_enabled }}"
  portainer_data_path: "/opt/portainer/data"
```

### 2. Host Variables (eu01.yml)

Host-specific configuration that overrides profile defaults:

```yaml
# Server identification
server_info:
  hostname: eu01
  environment: production
  location: germany
  datacenter: ansis_eu
  role: application_server
  timezone: "Europe/Berlin"

# Production domain configuration
domain_name: "portainer.eu01.ansis.com"
ssl_email: "admin@ansis.com"
ssl_enabled: true

# Secure Portainer configuration
portainer_admin_password: "{{ vault_portainer_admin_password }}"
portainer_domain: "{{ domain_name }}"
portainer_ssl_enabled: "{{ ssl_enabled }}"
portainer_data_path: "/opt/portainer/data"

# Production network configuration
portainer_network:
  name: "portainer_network"
  subnet: "172.20.0.0/16"
  gateway: "172.20.0.1"

# Enhanced container configuration
containers:
  portainer:
    image: "portainer/portainer-ce:latest"
    container_name: "portainer"
    restart_policy: "unless-stopped"
    ports:
      - "9000:9000"
      - "9443:9443"
    volumes:
      - "{{ portainer_data_path }}:/data"
      - "/var/run/docker.sock:/var/run/docker.sock"
    environment:
      PORTAINER_ADMIN_PASSWORD: "{{ portainer_admin_password }}"
      PORTAINER_DOMAIN: "{{ portainer_domain }}"
      PORTAINER_SSL_ENABLED: "{{ portainer_ssl_enabled }}"
    networks:
      - "{{ portainer_network.name }}"
    labels:
      traefik.enable: "true"
      traefik.http.routers.portainer.rule: "Host(`{{ portainer_domain }}`)"
      traefik.http.routers.portainer.tls: "true"
      traefik.http.routers.portainer.tls.certresolver: "letsencrypt"
      traefik.http.services.portainer.loadbalancer.server.port: "9000"
    deploy:
      resources:
        limits:
          memory: "256M"
          cpus: "0.5"
        reservations:
          memory: "128M"
          cpus: "0.25"

# Production security configuration
security:
  fail2ban_enabled: true
  ufw_enabled: true
  ssh_key_only: true
  disable_root_login: true

# Backup and monitoring
backup_config:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention_days: 30
  backup_path: "/opt/backups/portainer"
  s3_bucket: "eu01-portainer-backups"

monitoring:
  enabled: true
  metrics_port: 9090
  health_check_interval: "30s"
  log_level: "info"
```

## Variable Resolution Process

When deploying to `eu01`, Ansible resolves variables in this order:

1. **Profile defaults** (portainer.yml `vars` section)
2. **Host variables** (eu01.yml) - **OVERRIDES** profile defaults
3. **Runtime variables** (command line or playbook)

### Example Resolution:

| Variable | Profile Default | eu01.yml Override | Final Value |
|----------|----------------|-------------------|-------------|
| `domain_name` | `portainer.localhost` | `portainer.eu01.ansis.com` | `portainer.eu01.ansis.com` |
| `ssl_enabled` | `false` | `true` | `true` |
| `portainer_admin_password` | `admin123` | `{{ vault_portainer_admin_password }}` | Encrypted vault value |
| `portainer_network.subnet` | `172.20.0.0/16` | `172.20.0.0/16` | `172.20.0.0/16` |

## Deployment Commands

### 1. Deploy Portainer to eu01

```bash
# Deploy software packages and configuration
cstation server setup eu01 --profile portainer

# Deploy Docker containers
cstation server setup docker eu01
```

### 2. List Available Profiles

```bash
cstation server setup list-profiles
```

Output:
```
┌─────────────────┬────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
│ Profile         │ Description                                                │ Packages                                                       │ Docker Containers                                 │
├─────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ portainer       │ Lightweight profile for Portainer container management    │ docker.io, docker-compose, curl (+2 more)                    │ portainer                                         │
│                 │ interface with minimal software dependencies               │                                                                │                                                   │
└─────────────────┴────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

## Security Features

### 1. Encrypted Passwords

The `eu01.yml` uses Ansible Vault for sensitive data:

```yaml
vault_portainer_admin_password: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          66386439653162336464623061656366323464663934346662653462613431303866333966346662
          3835663566353936643834613633643561343864663531310a626438346336353331306338626235
          62643935633965316462663936396664313632633437343265656138643863393265373231323632
          3665626431626532650a353638643435666633633964366338653939323837643939343264626364
          3833
```

### 2. Firewall Configuration

```yaml
firewall_rules:
  - port: 22
    protocol: tcp
    rule: allow
    comment: "SSH access"
  - port: 9000
    protocol: tcp
    rule: allow
    comment: "Portainer HTTP"
  - port: 9443
    protocol: tcp
    rule: allow
    comment: "Portainer HTTPS"
```

## Benefits of This Setup

### 1. **Environment Separation**
- Development: Use profile defaults (localhost, no SSL)
- Production: Use host variables (custom domain, SSL, vault passwords)

### 2. **Reusability**
- Same profile works for multiple environments
- Host-specific customization without profile duplication

### 3. **Security**
- Sensitive data encrypted with Ansible Vault
- Environment-specific security configurations

### 4. **Maintainability**
- Profile defines the template
- Host variables contain environment-specific data
- Clear separation of concerns

## Advanced Customization

### Creating Additional Host Files

For different environments, create additional host variable files:

```bash
# Development environment
echo 'domain_name: "portainer.dev.local"' > etc/ansible/host_vars/dev01.yml

# Staging environment
echo 'domain_name: "portainer.staging.ansis.com"' > etc/ansible/host_vars/staging01.yml
```

### Custom Container Configuration

Override specific container settings in host variables:

```yaml
# In host_vars/eu01.yml
containers:
  portainer:
    deploy:
      resources:
        limits:
          memory: "512M"  # Increase memory for production
          cpus: "1.0"     # Increase CPU allocation
```

## Troubleshooting

### 1. Variable Not Resolving

```bash
# Check variable resolution
ansible-playbook -i inventory/production playbooks/portainer.yml --check --diff -v
```

### 2. Vault Password Issues

```bash
# Decrypt vault variable
ansible-vault decrypt_string '{{ vault_portainer_admin_password }}'

# Re-encrypt with new password
ansible-vault encrypt_string 'new_password' --name 'vault_portainer_admin_password'
```

### 3. Container Deployment Issues

```bash
# Check Docker status
docker ps -a | grep portainer

# Check container logs
docker logs portainer
```

This setup provides a robust, secure, and maintainable way to deploy Portainer across different environments while keeping configuration organized and environment-specific.