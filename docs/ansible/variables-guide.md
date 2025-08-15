# Ansible Variables Organization Guide

This guide explains the recommended approach for organizing configuration variables in Ansible for server and container management.

## Directory Structure

```
etc/ansible/
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