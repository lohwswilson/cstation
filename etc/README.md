# Configuration Directory

This directory contains all configuration files for CStation infrastructure management.

## Structure

### Ansible Configuration
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
# Run playbook with local inventory
cstation ansible playbook ./etc/ansible/playbooks/site.yml -i ./etc/ansible/inventory/hosts.yml

# Ping hosts using local inventory
cstation ansible ping -i ./etc/ansible/inventory/hosts.yml
```

### Docker
```bash
# Use compose file from etc directory
docker-compose -f ./etc/docker/compose/docker-compose.yml up -d
```
