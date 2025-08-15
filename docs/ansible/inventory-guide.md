# Ansible Inventory Management Guide

This guide explains how to use the improved Ansible inventory system with secure vault integration.

## Overview

The inventory has been restructured to provide:
- **Security**: Sensitive data moved to encrypted vault files
- **Organization**: Logical grouping of hosts and environments
- **Scalability**: Easy addition of new hosts and environments
- **Best Practices**: Following Ansible community standards

## Directory Structure

```
etc/ansible/
├── inventory/
│   └── hosts.yml          # Main inventory file
├── vault/
│   └── secrets.yml.template # Template for sensitive variables
└── group_vars/             # Group-specific variables (if needed)
```

## Inventory Structure

### Environment Groups

- **production**: Production servers (SYC_USA, SYC_SGP)
- **development**: Development and testing servers (LOCAL, ANSIS_SGP)

### Service Groups

- **postgresql_servers**: All servers running PostgreSQL
- **traefik_servers**: All servers running Traefik reverse proxy
- **portainer_servers**: All servers running Portainer container management

## Setting Up Vault

### 1. Create Vault File

```bash
# Copy the template
cp etc/ansible/vault/secrets.yml.template etc/ansible/vault/secrets.yml

# Edit the file and replace all CHANGE_ME_* values with actual secrets
vim etc/ansible/vault/secrets.yml
```

### 2. Encrypt the Vault

```bash
# Encrypt the vault file
ansible-vault encrypt etc/ansible/vault/secrets.yml

# You'll be prompted to create a vault password
```

### 3. Edit Encrypted Vault

```bash
# Edit the encrypted vault
ansible-vault edit etc/ansible/vault/secrets.yml
```

## Using the Inventory

### Running Playbooks

```bash
# Run against all production servers
ansible-playbook -i etc/ansible/inventory/hosts.yml --ask-vault-pass playbook.yml --limit production

# Run against specific service group
ansible-playbook -i etc/ansible/inventory/hosts.yml --ask-vault-pass playbook.yml --limit postgresql_servers

# Run against specific host
ansible-playbook -i etc/ansible/inventory/hosts.yml --ask-vault-pass playbook.yml --limit sg01.syc.com
```

### Using Vault Password File

```bash
# Create a vault password file (keep this secure!)
echo "your_vault_password" > .vault_pass
chmod 600 .vault_pass

# Use vault password file
ansible-playbook -i etc/ansible/inventory/hosts.yml --vault-password-file .vault_pass playbook.yml
```

## Vault Variables Reference

| Variable | Description | Used By |
|----------|-------------|----------|
| `vault_postgresql_password` | PostgreSQL database password | All PostgreSQL servers |
| `vault_local_sudo_password` | Local sudo password | Development environment |
| `vault_portainer_admin_password` | Portainer admin password | Portainer servers |
| `vault_traefik_pilot_token_sg01` | Traefik Pilot token for sg01 | sg01.syc.com |
| `vault_traefik_pilot_token_sg02` | Traefik Pilot token for sg02 | sg02.syc.com |

## Adding New Hosts

### 1. Add to Inventory

```yaml
# Add to appropriate environment group
production:
  hosts:
    new-server.example.com:
      ansible_host: 192.168.1.100
      ansible_user: admin
      # Add host-specific variables here
```

### 2. Add to Service Groups

```yaml
# Add to relevant service groups
postgresql_servers:
  hosts:
    new-server.example.com:
```

### 3. Add Vault Variables (if needed)

```bash
# Edit vault to add new secrets
ansible-vault edit etc/ansible/vault/secrets.yml
```

## Security Best Practices

1. **Never commit unencrypted secrets** to version control
2. **Use strong vault passwords** and store them securely
3. **Rotate vault passwords** regularly
4. **Limit vault access** to authorized personnel only
5. **Use separate vaults** for different environments if needed
6. **Backup vault files** securely

## Troubleshooting

### Common Issues

1. **Vault password prompt**: Use `--ask-vault-pass` or `--vault-password-file`
2. **Host unreachable**: Check `ansible_host` and network connectivity
3. **Permission denied**: Verify SSH keys and `ansible_user` settings
4. **Variable not found**: Ensure vault variables are properly defined

### Testing Connectivity

```bash
# Test connection to all hosts
ansible -i etc/ansible/inventory/hosts.yml all -m ping --ask-vault-pass

# Test specific group
ansible -i etc/ansible/inventory/hosts.yml production -m ping --ask-vault-pass
```

## Migration from Old Inventory

If you're migrating from the old inventory format:

1. **Backup** your current inventory
2. **Extract secrets** from the old inventory
3. **Add secrets** to the vault file
4. **Test connectivity** with the new inventory
5. **Update playbooks** to use new group names if needed

## Example Playbook Usage

```yaml
---
- name: Deploy application
  hosts: production
  become: yes
  vars_files:
    - etc/ansible/vault/secrets.yml
  tasks:
    - name: Configure PostgreSQL
      postgresql_user:
        name: myapp
        password: "{{ vault_postgresql_password }}"
        # ... other tasks
```

This improved inventory system provides a solid foundation for managing your infrastructure with Ansible while maintaining security and organization.