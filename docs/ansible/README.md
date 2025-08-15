# Ansible Configuration Guide

This directory contains the improved Ansible configuration for the CStation infrastructure management system.

## Overview

The Ansible setup has been enhanced with:
- **Secure vault integration** for sensitive data
- **Organized inventory structure** with logical groupings
- **Optimized configuration** for better performance
- **Comprehensive documentation** for easy maintenance

## Directory Structure

```
etc/ansible/
├── ansible.cfg              # Main Ansible configuration
├── inventory/
│   └── hosts.yml            # Improved inventory with vault integration
├── vault/
│   └── secrets.yml.template # Template for sensitive variables
├── roles/                   # Ansible roles (if any)
└── collections/             # Ansible collections (if any)
```

## Key Improvements

### 1. Security Enhancements

- **Vault Integration**: All sensitive data moved to encrypted vault files
- **Template System**: Secure template for managing secrets
- **No Plain Text Passwords**: All credentials properly encrypted

### 2. Inventory Organization

- **Environment Groups**: `production` and `development` for clear separation
- **Service Groups**: `postgresql_servers`, `traefik_servers`, `portainer_servers`
- **Consistent Naming**: Clear, descriptive host and group names
- **Scalable Structure**: Easy to add new hosts and environments

### 3. Configuration Optimizations

- **Performance**: SSH multiplexing, pipelining, and smart fact gathering
- **User Experience**: Better output formatting with colors and YAML callback
- **Reliability**: Connection retries and proper timeouts
- **Development Friendly**: Disabled host key checking for easier testing

## Quick Start

### 1. Set Up Vault

```bash
# Navigate to the ansible directory
cd etc/ansible

# Copy and customize the vault template
cp vault/secrets.yml.template vault/secrets.yml
vim vault/secrets.yml  # Replace all CHANGE_ME_* values

# Encrypt the vault
ansible-vault encrypt vault/secrets.yml
```

### 2. Test Connectivity

```bash
# Test connection to all hosts
ansible all -m ping --ask-vault-pass

# Test specific environment
ansible production -m ping --ask-vault-pass
```

### 3. Run Playbooks

```bash
# Run against production servers
ansible-playbook playbook.yml --limit production --ask-vault-pass

# Run against specific service group
ansible-playbook playbook.yml --limit postgresql_servers --ask-vault-pass
```

## Configuration Files

### ansible.cfg

The main configuration file includes:
- Optimized SSH settings for better performance
- Vault integration support
- Better output formatting
- Development-friendly defaults

### hosts.yml

The inventory file features:
- Environment-based grouping (production/development)
- Service-based grouping (postgresql/traefik/portainer)
- Vault variable references for sensitive data
- Clear host definitions with proper variables

### secrets.yml.template

A template for managing sensitive variables:
- Database passwords
- System credentials
- API tokens
- SSL certificates
- Third-party service credentials

## Vault Variables

| Variable | Purpose | Used By |
|----------|---------|----------|
| `vault_postgresql_password` | PostgreSQL database password | All PostgreSQL servers |
| `vault_local_sudo_password` | Local development sudo password | Development environment |
| `vault_portainer_admin_password` | Portainer admin password | Portainer servers |
| `vault_traefik_pilot_token_sg01` | Traefik Pilot token for sg01 | sg01.syc.com |
| `vault_traefik_pilot_token_sg02` | Traefik Pilot token for sg02 | sg02.syc.com |

## Best Practices

### Security
- Always encrypt vault files before committing
- Use strong vault passwords
- Rotate credentials regularly
- Never commit unencrypted secrets

### Organization
- Group hosts by environment and service
- Use descriptive variable names
- Document all custom variables
- Keep inventory structure consistent

### Performance
- Use SSH multiplexing for faster connections
- Enable pipelining for better throughput
- Cache facts when possible
- Limit playbook scope with `--limit`

## Troubleshooting

### Common Issues

1. **Vault Password Errors**
   ```bash
   # Use vault password file
   echo "your_password" > .vault_pass
   chmod 600 .vault_pass
   ansible-playbook playbook.yml --vault-password-file .vault_pass
   ```

2. **SSH Connection Issues**
   ```bash
   # Test SSH connectivity
   ssh -o StrictHostKeyChecking=no user@hostname
   
   # Check ansible connectivity
   ansible hostname -m ping -vvv
   ```

3. **Inventory Issues**
   ```bash
   # List all hosts
   ansible-inventory --list
   
   # Check specific group
   ansible-inventory --list --limit production
   ```

### Debug Commands

```bash
# Verbose output
ansible-playbook playbook.yml -vvv

# Check syntax
ansible-playbook playbook.yml --syntax-check

# Dry run
ansible-playbook playbook.yml --check

# List tasks
ansible-playbook playbook.yml --list-tasks
```

## Migration Guide

If migrating from the old inventory:

1. **Backup** existing configuration
2. **Extract secrets** from old inventory
3. **Create vault file** with extracted secrets
4. **Update playbooks** to use new group names
5. **Test thoroughly** before production use

## Additional Resources

- [Inventory Guide](inventory-guide.md) - Detailed inventory management
- [Variables Guide](variables-guide.md) - Ansible variables documentation
- [Ansible Documentation](https://docs.ansible.com/) - Official Ansible docs

This improved Ansible setup provides a solid foundation for infrastructure management with security, performance, and maintainability in mind.