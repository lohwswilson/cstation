# Docker Service Management

The `cstation service docker` command provides Docker container deployment and management capabilities using Ansible playbooks.

## Commands

### List Available Profiles

```bash
cstation service docker ls
```

Lists all available Docker service profiles (Ansible playbooks) in the `/etc/cstation/service/docker/` directory.

**Output:**
- Playbook name
- Description (extracted from comments)
- File size
- Last modified timestamp

**Example:**
```
Available Docker service profiles:

┌─────────────────┬─────────────────────────────────────┬──────────┬─────────────────────┐
│ Profile         │ Description                         │ Size     │ Last Modified       │
├─────────────────┼─────────────────────────────────────┼──────────┼─────────────────────┤
│ traefik         │ Traefik reverse proxy service       │ 1.2 KB   │ 2024-01-15 10:30:45 │
│ portainer       │ Portainer Docker management UI      │ 0.8 KB   │ 2024-01-14 15:22:10 │
│ portainer_agent │ Portainer Agent for remote mgmt     │ 0.6 KB   │ 2024-01-16 09:15:30 │
└─────────────────┴─────────────────────────────────────┴──────────┴─────────────────────┘
```

### Deploy Docker Service

```bash
cstation service docker push <profile> <target_host>
```

Deploys a Docker service using the specified Ansible playbook to a target host.

**Parameters:**
- `<profile>`: Name of the Docker service profile (without .yml extension)
- `<target_host>`: Target host from the inventory

**Features:**
- Automatically appends `.yml` extension if not provided
- Validates target host exists in inventory
- Executes Ansible playbook with proper environment setup
- Provides detailed output and error handling

**Example:**
```bash
# Deploy Traefik to eu01 server
cstation service docker push traefik eu01

# Deploy Portainer to us01 server  
cstation service docker push portainer us01

# Deploy Portainer Agent to remote server for centralized management
cstation service docker push portainer_agent eu02
```

**Output:**
```
[INFO] Executing Ansible playbook: traefik.yml on target: eu01
[INFO] Host 'eu01' found in inventory
[INFO] Starting playbook execution...

PLAY [Deploy Traefik Container] **************************************************

TASK [Create traefik directory] ***********************************************
ok: [eu01]

TASK [Create Docker network] *************************************************
changed: [eu01]

TASK [Deploy Traefik container] **********************************************
changed: [eu01]

PLAY RECAP ******************************************************************
eu01                       : ok=3    changed=2    unreachable=0    failed=0

[SUCCESS] Ansible playbook executed successfully
```

## Available Docker Services

### Portainer vs Portainer Agent

**Portainer (Full UI)**
- Complete Docker management interface
- Runs on ports 8000, 9000, and 9443
- Suitable for standalone Docker hosts or primary management server
- Includes web UI, API, and all management features

**Portainer Agent**
- Lightweight agent for remote Docker management
- Runs on port 9001
- Designed to be managed by a central Portainer instance
- Minimal resource footprint
- Ideal for remote servers in a distributed setup

### When to Use Each

- **Use Portainer** when you need a standalone Docker management UI or want to set up the primary management server
- **Use Portainer Agent** when you want to manage remote Docker hosts from a central Portainer instance

### Typical Architecture

```
[Main Server]     [Remote Servers]
Portainer UI  --> Portainer Agent (Server 1)
(Port 9000)   --> Portainer Agent (Server 2)
              --> Portainer Agent (Server N)
```

## See Also

- [Services Overview](../services/README.md) - Complete guide to all available Docker services
- [Portainer Setup Guide](../setup/PORTAINER_SETUP_GUIDE.md) - Full Portainer deployment guide
- [Portainer Agent Setup Guide](../setup/PORTAINER_AGENT_SETUP_GUIDE.md) - Remote management agent setup
- [Service Management](service.md) - General service management commands
- [Server Management](server.md) - Managing target servers and inventory
