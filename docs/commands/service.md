# Service Management Commands

The `cstation service` command provides service deployment and management capabilities using Ansible playbooks.

## Commands

### Server Service Management

#### List Available Server Profiles

```bash
cstation service server ls
```

Lists all available server service profiles (Ansible playbooks) in the `/etc/cstation/service/server/` directory.

**Output:**
- Profile name (without .yml extension)
- Description (extracted from comments)
- File size
- Last modified timestamp

**Example:**
```
                  Available Server Playbooks                   
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Playbook   ┃ Description          ┃ Size       ┃ Modified   ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ server.4GB │ Basic Server Profile │ 3025 bytes │ 1755446578 │
└────────────┴──────────────────────┴────────────┴────────────┘
```

#### Deploy Server Service

```bash
cstation service server push <profile> <target_host>
```

Deploy a server service profile to a specific target host using Ansible.

**Arguments:**
- `profile` - Server profile name (without .yml extension)
- `target_host` - Target hostname from the Ansible inventory

**Features:**
- Automatically appends `.yml` extension if not provided
- Validates target host exists in inventory
- Executes Ansible playbook with proper environment setup
- Provides detailed output and error handling

**Examples:**
```bash
# Deploy server.4GB profile to us01 server
cstation service server push server.4GB us01

# Deploy basic profile to eu01 server  
cstation service server push basic eu01
```

**Output:**
```
[INFO] Running playbook 'server.4GB.yml' on us01...
[INFO] Host 'us01' found in inventory
[INFO] Starting playbook execution...

PLAY [Deploy Server Configuration] *******************************************

TASK [Install required packages] ********************************************
ok: [us01]

TASK [Configure services] ****************************************************
changed: [us01]

TASK [Deploy configuration files] *******************************************
changed: [us01]

PLAY RECAP ******************************************************************
us01                       : ok=3    changed=2    unreachable=0    failed=0

[SUCCESS] Successfully executed playbook 'server.4GB.yml' on us01
```

## How it Works

1. **Profile Validation**: Checks if the specified profile exists in the service directory
2. **Host Validation**: Validates that the target host exists in the Ansible inventory
3. **Extension Handling**: Automatically appends `.yml` extension if not provided
4. **Ansible Execution**: Runs the Ansible playbook with proper environment configuration
5. **Output Processing**: Provides detailed feedback on execution status and results

## Requirements

- Ansible must be installed and accessible via `ansible-playbook` command
- Target server must be defined in the Ansible inventory
- Service profiles must exist in `/etc/cstation/service/server/`
- CLI automatically uses `/etc/cstation/ansible/ansible.cfg` configuration for all Ansible operations

## Troubleshooting

### Common Issues

1. **"Ansible not found"**
   - Install Ansible: `pip install ansible`

2. **"Ansible playbook not found"**
   - Verify profile exists: `cstation service server ls`
   - Check profile name spelling and case sensitivity

3. **"Host not found in inventory"**
   - Verify hostname exists in inventory: `cstation server list`
   - Check inventory file path and configuration

4. **"Permission denied"**
   - Ensure you have access to the target server
   - Check if the target user has appropriate privileges

5. **"Playbook execution failed"**
   - Review Ansible output for specific error details
   - Check target server connectivity and configuration
   - Verify playbook syntax and variable definitions