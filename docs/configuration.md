# Configuration Guide

CStation uses a structured configuration system located in `/etc/cstation/`. This guide covers how to configure and customize your CStation setup.

## Configuration File Ownership

CStation supports two ownership modes that affect how you edit configuration files:

- **Production Mode**: Files owned by root, requires `sudo` for editing
- **Developer Mode**: Files owned by current user, allows editing without `sudo`

See the [Init Command Documentation](commands/init.md) for details on switching between modes.

## Directory Structure

This directory contains all configuration files for CStation infrastructure management.

## Structure

### Ansible Configuration
- `ansible/ansible.cfg` - Main Ansible configuration (automatically used by CLI commands)
- `ansible/inventory/` - Ansible inventory files
- `ansible/group_vars/` - Group variables
- `ansible/host_vars/` - Host variables  
- `ansible/playbooks/` - Ansible playbooks
- `ansible/roles/` - Ansible roles

## Usage Examples

### Ansible
```bash
# CLI commands automatically use /etc/cstation/ansible/ansible.cfg configuration
# Setup SSH keys (uses ansible.cfg automatically)
cstation server ssh sg01



# Manual ansible commands (if needed)
ANSIBLE_CONFIG=/etc/cstation/ansible/ansible.cfg ansible-inventory --list
ANSIBLE_CONFIG=/etc/cstation/ansible/ansible.cfg ansible-playbook playbook.yml
```
