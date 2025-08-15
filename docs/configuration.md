# Configuration Directory

This directory contains all configuration files for CStation infrastructure management.

## Structure

### Ansible Configuration
- `ansible/ansible.cfg` - Main Ansible configuration (automatically used by CLI commands)
- `ansible/inventory/` - Ansible inventory files
- `ansible/group_vars/` - Group variables
- `ansible/host_vars/` - Host variables  
- `ansible/playbooks/` - Ansible playbooks
- `ansible/roles/` - Ansible roles

### Docker Configuration
- `docker/compose/` - Docker Compose files
- `docker/configs/` - Docker configuration files

## Usage Examples

### Ansible
```bash
# CLI commands automatically use etc/ansible/ansible.cfg configuration
# Run server setup (uses ansible.cfg automatically)
cstation server setup sg01 --profile database_server

# Setup SSH keys (uses ansible.cfg automatically)
cstation server ssh sg01

# Deploy containers (uses ansible.cfg automatically)
cstation docker deploy sg01 --profile web_server

# Manual ansible commands (if needed)
ANSIBLE_CONFIG=etc/ansible/ansible.cfg ansible-inventory --list
ANSIBLE_CONFIG=etc/ansible/ansible.cfg ansible-playbook playbook.yml
```

### Docker
```bash
# Use compose file from etc directory
docker-compose -f ./etc/docker/compose/docker-compose.yml up -d
```
