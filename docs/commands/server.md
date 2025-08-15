# Server Command Module

The `server` command provides remote server management capabilities for CStation CLI.

## Features

### SSH Key Setup

Automatically configure SSH key authentication on remote servers using Ansible.

### Server Status & Health Monitoring

Check server status, health, and uptime information using Ansible.

### Server Inventory Management

List and manage servers from Ansible inventory.

## Commands

### `cstation server ssh <hostname>`

Setup SSH key authentication for a remote server.

**Arguments:**
- `hostname` - Target hostname from the Ansible inventory

**Options:**
- `-i, --inventory` - Inventory file path (default: `etc/ansible/inventory/hosts.yml`)
- `-k, --key-path` - Path to SSH public key (default: `~/.ssh/id_rsa.pub`)
- `--generate` - Generate new SSH key pair if not exists

**Examples:**

```bash
# Setup SSH key for sg01 server
cstation server ssh sg01

# Setup SSH key with custom inventory file
cstation server ssh sg01 -i /path/to/inventory.yml

# Setup SSH key with custom key path
cstation server ssh sg01 -k ~/.ssh/my_key.pub

# Generate new SSH key and setup
cstation server ssh sg01 --generate
```

### `cstation server status [hostname]`

Check server status, health, and uptime using Ansible.

**Arguments:**
- `hostname` - Target hostname from inventory (optional - shows all if not specified)

**Options:**
- `-i, --inventory` - Inventory file path (default: `etc/ansible/inventory/hosts.yml`)
- `--services` - Check common services status (docker, nginx, etc.)
- `--uptime/--no-uptime` - Include uptime information in status check (default: enabled)

**Examples:**

```bash
# Check status of all servers
cstation server status

# Check status of specific server
cstation server status sg01

# Check status with services information
cstation server status --services

# Check status without uptime information
cstation server status --no-uptime

# Check status with custom inventory
cstation server status -i /path/to/inventory.yml
```

### `cstation server list`

List servers from Ansible inventory in a formatted table.

**Options:**
- `-i, --inventory` - Inventory file path (default: `etc/ansible/inventory/hosts.yml`)
- `--detail` - Show detailed host information

**Examples:**

```bash
# List all servers
cstation server list

# List servers with detailed information
cstation server list --detail

# List servers from custom inventory
cstation server list -i /path/to/inventory.yml
```

## How it Works

1. **Key Validation**: Checks if the specified SSH public key exists
2. **Key Generation**: Optionally generates a new SSH key pair if requested
3. **Ansible Playbook**: Creates and runs a temporary Ansible playbook that:
   - Ensures `.ssh` directory exists on the target server
   - Adds the public key to `authorized_keys`
   - Tests the SSH connection
4. **Cleanup**: Removes temporary files after execution

## Requirements

- Ansible must be installed and accessible via `ansible-playbook` command
- Target server must be defined in the Ansible inventory
- Initial access to the target server (password or existing key)
- CLI automatically uses `etc/ansible/ansible.cfg` configuration for all Ansible operations

## Security Notes

- SSH keys are generated with RSA 4096-bit encryption
- Private keys are created without passphrase for automation purposes
- Public keys are safely added to authorized_keys without overwriting existing entries
- Temporary playbook files are automatically cleaned up after execution

## Troubleshooting

### Common Issues

1. **"ansible-playbook command not found"**
   - Install Ansible: `pip install ansible`

2. **"SSH public key not found"**
   - Use `--generate` flag to create a new key pair
   - Or specify existing key with `-k` option

3. **"Host not found in inventory"**
   - Verify hostname exists in inventory: `cstation ansible inventory list`
   - Check inventory file path with `-i` option

4. **"Permission denied"**
   - Ensure you have initial access to the target server
   - Check if the target user has sudo privileges