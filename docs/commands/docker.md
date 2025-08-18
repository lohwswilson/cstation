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

┌─────────────┬─────────────────────────────────────┬──────────┬─────────────────────┐
│ Profile     │ Description                         │ Size     │ Last Modified       │
├─────────────┼─────────────────────────────────────┼──────────┼─────────────────────┤
│ traefik     │ Traefik reverse proxy service       │ 1.2 KB   │ 2024-01-15 10:30:45 │
│ portainer   │ Portainer Docker management UI      │ 0.8 KB   │ 2024-01-14 15:22:10 │
└─────────────┴─────────────────────────────────────┴──────────┴─────────────────────┘
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

```
