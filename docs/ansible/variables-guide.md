# Ansible Variables Organization Guide

This guide explains the recommended approach for organizing configuration variables in Ansible for server and container management.

## Directory Structure

```
/etc/cstation/ansible/
├── group_vars/
│   ├── all.yml                    # Global variables for all hosts
│   ├── database_servers.yml       # Variables for database server group
│   ├── web_servers.yml            # Variables for web server group
│   ├── production.yml             # Environment-specific variables
│   ├── staging.yml                # Staging environment variables
│   └── development.yml            # Development environment variables
├── host_vars/
│   ├── sg01.yml                   # Host-specific variables for sg01
│   ├── sg02.yml                   # Host-specific variables for sg02
│   └── us01.yml                   # Host-specific variables for us01
└── inventory/
    └── hosts.yml                  # Inventory with group definitions
```

## Variable Precedence (Highest to Lowest)

1. **host_vars/hostname.yml** - Host-specific variables
2. **group_vars/groupname.yml** - Group-specific variables
3. **group_vars/all.yml** - Global variables
4. **Inventory variables** - Variables defined in inventory file

## Recommended Organization

### 1. Global Variables (`group_vars/all.yml`)

Define variables that apply to ALL hosts:
- Common Docker settings
- Security baseline configurations
- Standard packages
- Default timezone and locale
- Common service ports

### 2. Group Variables (`group_vars/`)

Organize by:
- **Server Role**: `database_servers.yml`, `web_servers.yml`, `app_servers.yml`
- **Environment**: `production.yml`, `staging.yml`, `development.yml`
- **Location**: `singapore.yml`, `usa.yml`, `europe.yml`

### 3. Host Variables (`host_vars/hostname.yml`)

Define host-specific configurations:
- Container definitions and configurations
- Hardware-specific settings
- Host-unique identifiers
- Custom overrides for group variables

## Container Configuration Best Practices

### Structure for Container Variables

```yaml
containers:
  service_name:
    name: "{{ container_name_variable }}"
    image: "image:tag"
    ports:
      - "host_port:container_port"
    volumes:
      - "host_path:container_path"
    environment:
      ENV_VAR: "value"
    networks:
      - "network_name"
    restart_policy: always
    resource_limits:
      cpu: "1000m"
      memory: "2Gi"
```

### Example: PostgreSQL Container Configuration

```yaml
# In host_vars/sg01.yml
containers:
  postgresql:
    name: "{{ postgresql_container }}"
    image: "{{ postgresql_docker_image }}"
    ports:
      - "{{ postgresql_port }}:5432"
    environment:
      POSTGRES_DB: "{{ postgresql_db_admin }}"
      POSTGRES_USER: "{{ postgresql_db_admin }}"
      POSTGRES_PASSWORD: "{{ postgresql_db_password }}"
    volumes:
      - "postgresql_data:/var/lib/postgresql/data"
      - "./config/postgresql.conf:/etc/postgresql/postgresql.conf"
    networks:
      - "{{ docker_network }}"
```

## Variable Naming Conventions

### 1. Use Descriptive Names
- ✅ `postgresql_max_connections`
- ❌ `pg_max_conn`

### 2. Group Related Variables
```yaml
postgresql_settings:
  version: "16"
  port: 5432
  max_connections: 200
  shared_buffers: "256MB"
```

### 3. Use Environment Prefixes
- `prod_database_url`
- `staging_api_key`
- `dev_debug_mode`

## Security Considerations

### 1. Use Ansible Vault for Secrets
```bash
# Create encrypted variables
ansible-vault create group_vars/all/vault.yml

# Edit encrypted file
ansible-vault edit group_vars/all/vault.yml
```

### 2. Reference Vault Variables
```yaml
# In vault.yml
vault_postgresql_password: "super_secret_password"
vault_api_key: "secret_api_key"

# In regular variables
postgresql_password: "{{ vault_postgresql_password }}"
api_key: "{{ vault_api_key }}"
```

## Template Integration

Variables automatically available in Jinja2 templates:

```jinja2
# In templates/postgresql/postgresql.conf.j2
max_connections = {{ postgresql_settings.max_connections }}
shared_buffers = {{ postgresql_settings.shared_buffers }}
port = {{ postgresql_settings.port }}

# Host-specific values
listen_addresses = '{{ ansible_default_ipv4.address }}'
```

## Dynamic Inventory Integration

Variables can be sourced from:
- Cloud provider APIs
- CMDB systems
- External configuration management

```yaml
# Example dynamic variables
cloud_metadata:
  instance_type: "{{ ec2_instance_type }}"
  availability_zone: "{{ ec2_placement_availability_zone }}"
  security_groups: "{{ ec2_security_groups }}"
```

## Validation and Testing

### 1. Variable Validation in Playbooks
```yaml
- name: Validate required variables
  assert:
    that:
      - postgresql_password is defined
      - postgresql_password | length > 8
    fail_msg: "PostgreSQL password must be defined and at least 8 characters"
```

### 2. Testing with Different Variable Sets
```bash
# Test with specific inventory
ansible-playbook -i inventory/production playbook.yml

# Test with extra variables
ansible-playbook playbook.yml -e "environment=staging"
```

## Migration from Current Setup

1. **Extract common variables** from inventory to `group_vars/all.yml`
2. **Create group-specific files** for server roles
3. **Move host-specific variables** to `host_vars/`
4. **Implement vault** for sensitive data
5. **Update templates** to use new variable structure
6. **Test thoroughly** before production deployment

## Example Commands

```bash
# Run playbook with specific group variables
ansible-playbook -i inventory/hosts.yml setup.yml --limit database_servers

# Override variables at runtime
ansible-playbook setup.yml -e "postgresql_version=15"

# Use vault password file
ansible-playbook setup.yml --vault-password-file ~/.ansible_vault_pass
```

This organization provides:
- ✅ Clear separation of concerns
- ✅ Easy maintenance and updates
- ✅ Secure secret management
- ✅ Flexible environment management
- ✅ Scalable configuration structure

## CStation: PostgreSQL authentication policy and variables

This section documents the recommended PostgreSQL authentication setup used by the CStation Docker playbook (etc/ansible/playbooks/docker/postgresql.yml) and the variables you should define in host_vars/group_vars.

### Policy overview

- Local connections (UNIX socket and localhost) use password-based authentication with scram-sha-256 for all users, including the postgres superuser.
- Remote connections are disabled by default; if enabled, only explicitly whitelisted networks are allowed and must use scram-sha-256.
- Catch-all rules are set to reject for both IPv4 and IPv6 to prevent unintended access.
- Optional TLS: if ssl_enabled is true, remote rules render as hostssl; otherwise host.

### Inventory variables

Define these under host_vars/<host>.yml or group_vars:

```yaml
postgresql:
  version: "18"                     # Docker image tag
  container_name: "{{ inventory_hostname | upper }}_DB"
  docker_image: "postgres:{{ postgresql.version }}"
  port: 1488                         # Host port mapped to container 5432
  db_admin: "postgres"              # Admin user
  db_password: "<strong-secret>"    # Admin password (use Ansible Vault in production)
  database: "postgres"              # Default DB for health checks
  data_dir: "/var/lib/postgresql/{{ inventory_hostname | upper }}_DB/data"
  config_dir: "/etc/postgresql/{{ inventory_hostname | upper }}_DB/"

  # Authentication policy
  local_auth_method: scram-sha-256   # Local socket and localhost
  remote_auth_method: scram-sha-256  # Remote connections (if enabled)
  ssl_enabled: "off"                 # "on" renders hostssl rules; "off" renders host
  allow_remote_connections: true     # Enable remote access only for allowed networks
  allowed_networks:
    - "172.18.0.0/16"               # Whitelisted CIDR(s)
```

Example: sg07 host variables

```yaml
# etc/ansible/inventory/host_vars/sg07.yml
postgresql:
  version: "18"
  container_name: "{{ inventory_hostname | upper }}_DB"
  docker_image: "postgres:{{ postgresql.version }}"
  port: 1488
  db_admin: "postgres"
  db_password: "wai39kua"           # Replace with your vault reference in production
  database: "postgres"
  data_dir: "/var/lib/postgresql/{{ inventory_hostname | upper }}_DB/data"
  config_dir: "/etc/postgresql/{{ inventory_hostname | upper }}_DB/"
  local_auth_method: scram-sha-256
  remote_auth_method: scram-sha-256
  ssl_enabled: "off"
  allow_remote_connections: true
  allowed_networks:
    - "172.18.0.0/16"
```

### Rendered pg_hba.conf (effective rules)

The template `etc/ansible/playbooks/docker/templates/postgresql/pg_hba.conf.j2` renders to:

```
local   all     postgres                        scram-sha-256
local   all     all                             scram-sha-256
host    all     all     127.0.0.1/32            scram-sha-256
host    all     all     ::1/128                 scram-sha-256
host    all     all     172.18.0.0/16           scram-sha-256   # only if allow_remote_connections=true
host    all     all     0.0.0.0/0               reject
host    all     all     ::/0                    reject
```

If `ssl_enabled: "on"`, the remote rules render as `hostssl` instead of `host`.

### Deployment commands

Run the Docker PostgreSQL playbook to (re)deploy configuration and container:

```bash
bin/ansible-playbook -i etc/ansible/inventory/hosts.yml \
  etc/ansible/playbooks/docker/postgresql.yml -l sg07
```

Notes:
- The playbook validates memory/disk and templates, deploys postgresql.conf, pg_hba.conf, and auto.conf, and recreates the container when configs change.
- Health checks run via pg_isready using the configured admin user/password.

### Verification tests

From the SG07 host (inside container):

```bash
# TCP localhost with password
docker exec SG07_DB env PGPASSWORD=<password> psql -h 127.0.0.1 -U postgres -d postgres \
  -c "SELECT current_user, inet_server_addr();"

# UNIX socket with password
docker exec SG07_DB env PGPASSWORD=<password> psql -U postgres -d postgres \
  -c "SELECT current_user;"
```

From the host (outside container):

```bash
psql -h localhost -p 1488 -U postgres -d postgres
# Enter the password when prompted
```

### Password management and rotation

- To set/rotate the postgres user password in the running container:

```bash
docker exec -u postgres -it SG07_DB psql -c "ALTER ROLE postgres WITH PASSWORD 'NEW_PASSWORD';"
```

- Update `postgresql.db_password` in `host_vars/<host>.yml` (ideally referencing an Ansible Vault variable in production).

### Security hardening tips

- Avoid `trust` or `peer` for production environments.
- Keep catch-all rules as `reject` and only allow explicit networks.
- Prefer `scram-sha-256` for both local and remote authentication.
- Use `hostssl` when TLS is configured and required.