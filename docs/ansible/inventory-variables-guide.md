# Inventory Variables Guide

This guide explains how to properly structure variables in the `/etc/ansible/inventory` directory for cstation deployments.

## Directory Structure

The recommended inventory structure is:

```
/etc/ansible/inventory/
├── hosts.yml                 # Main inventory file
├── group_vars/
│   ├── all.yml              # Variables for all hosts
│   ├── docker.yml           # Variables for docker group
│   └── servers.yml          # Variables for servers group
└── host_vars/
    ├── server1.yml          # Variables specific to server1
    ├── server2.yml          # Variables specific to server2
    └── server1/
        └── vault.yml        # Encrypted sensitive data for server1
```

## Variable Precedence

Ansible follows this variable precedence order (highest to lowest):
1. `host_vars/<hostname>.yml` - Host-specific variables
2. `group_vars/<groupname>.yml` - Group-specific variables
3. `group_vars/all.yml` - Variables for all hosts
4. Playbook variables
5. Default variables

## PgAdmin Container Variables

For the PgAdmin container deployment, create a host_vars file for each target host:

### Example: `/etc/ansible/inventory/host_vars/myserver.yml`

```yaml
# PgAdmin Container Configuration
pgadmin:
  container_name: "{{ inventory_hostname|upper }}_PGADMIN"
  image: "dpage/pgadmin4:latest"
  port: "5050"
  network_name: "PW_NET"
  
  # Volume configurations
  data_volume: "/var/lib/perfectwork/{{ inventory_hostname|upper }}/DB/{{ inventory_hostname|upper }}_PGADMIN"
  servers_config: "/tmp/servers.json"
  
  # Credentials (reference vault variables)
  default_email: "pgadmin@synercatalyst.com"
  default_password: "{{ vault_pgadmin_password }}"
  
  # Traefik configuration
  traefik:
    enable: "true"
    certresolver: "le_resolver"
    host: "pgadmin.synercatalyst.com"
    service_port: "80"
```

### Securing Sensitive Data with Ansible Vault

1. **Create a vault file for sensitive data:**
   ```bash
   ansible-vault create /etc/ansible/inventory/host_vars/myserver/vault.yml
   ```

2. **Add sensitive variables to the vault file:**
   ```yaml
   vault_pgadmin_password: "your_secure_password_here"
   vault_pgadmin_email: "admin@yourcompany.com"
   ```

3. **Reference vault variables in your host_vars:**
   ```yaml
   pgadmin:
     default_email: "{{ vault_pgadmin_email }}"
     default_password: "{{ vault_pgadmin_password }}"
   ```

4. **Run playbooks with vault password:**
   ```bash
   cstation service docker push docker_pgadmin --ask-vault-pass
   # or
   cstation service docker push docker_pgadmin --vault-password-file ~/.vault_pass
   ```

## Best Practices

1. **Never commit sensitive data in plain text**
   - Always use Ansible Vault for passwords, API keys, and certificates
   - Add `*.yml` files containing sensitive data to `.gitignore`

2. **Use consistent variable naming**
   - Group related variables under a common namespace (e.g., `pgadmin.*`)
   - Use descriptive variable names

3. **Environment-specific configurations**
   - Use group_vars for environment-wide settings (dev, staging, prod)
   - Use host_vars for host-specific overrides

4. **Documentation**
   - Document variable purposes and expected values
   - Provide examples for complex variable structures

## Common Variable Patterns

### Docker Container Variables
```yaml
container_name:
  name: "service_name"
  image: "image:tag"
  ports:
    - "host_port:container_port"
  volumes:
    - "host_path:container_path"
  environment:
    VAR_NAME: "value"
  networks:
    - "network_name"
```

### Traefik Labels
```yaml
traefik:
  enable: "true"
  host: "service.domain.com"
  certresolver: "le_resolver"
  service_port: "80"
```

## Troubleshooting

- **Variable not found errors**: Check variable precedence and file locations
- **Vault decryption errors**: Ensure correct vault password is provided
- **Template errors**: Verify Jinja2 syntax in variable references
- **Host not found**: Check inventory file and host group assignments