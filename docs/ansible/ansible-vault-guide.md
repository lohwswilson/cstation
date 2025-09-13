# Ansible Vault Guide

Ansible Vault is a feature that allows you to encrypt sensitive data such as passwords, API keys, and certificates. This guide shows how to use Ansible Vault with cstation.

## What is Ansible Vault?

Ansible Vault encrypts variables and files so you can protect sensitive content rather than leaving it visible as plaintext. You can encrypt:
- Individual variables
- Entire files
- Structured data (YAML/JSON)

## Basic Vault Commands

### Creating a New Encrypted File
```bash
# Create a new encrypted file
ansible-vault create /etc/ansible/inventory/host_vars/us01/vault.yml

# You'll be prompted to enter a vault password
# Then an editor will open for you to add content
```

### Editing an Encrypted File
```bash
# Edit an existing encrypted file
ansible-vault edit /etc/ansible/inventory/host_vars/us01/vault.yml
```

### Encrypting an Existing File
```bash
# Encrypt an existing plaintext file
ansible-vault encrypt /etc/ansible/inventory/host_vars/us01/secrets.yml
```

### Decrypting a File
```bash
# Decrypt a file (makes it plaintext)
ansible-vault decrypt /etc/ansible/inventory/host_vars/us01/vault.yml

# View encrypted file content without decrypting
ansible-vault view /etc/ansible/inventory/host_vars/us01/vault.yml
```

### Changing Vault Password
```bash
# Change the password of an encrypted file
ansible-vault rekey /etc/ansible/inventory/host_vars/us01/vault.yml
```

## Using Vault with CStation

### 1. Directory Structure for Vault Files

#### Option A: Single Centralized Vault File (Recommended for Small Teams)

```
/etc/ansible/inventory/
├── hosts.yml
├── vault.yml                  # Single vault file for all secrets
├── group_vars/
│   └── all.yml
└── host_vars/
    ├── us01.yml               # Regular variables
    ├── eu01.yml
    └── prod01.yml
```

#### Option B: Multiple Host-Specific Vault Files (Recommended for Large Teams)

```
/etc/ansible/inventory/
├── hosts.yml
├── group_vars/
│   ├── all.yml
│   └── all/
│       └── vault.yml          # Group-wide secrets
└── host_vars/
    ├── us01.yml               # Regular variables
    ├── us01/
    │   └── vault.yml          # Host-specific secrets
    ├── eu01.yml
    └── eu01/
        └── vault.yml
```

### 2. Example Vault File Content

#### Single Centralized Vault File

Create `/etc/ansible/inventory/vault.yml`:

```yaml
# Centralized vault file for all environments and hosts
# PgAdmin credentials
vault_pgadmin_password: "SuperSecurePassword123!"
vault_pgadmin_email: "admin@company.com"

# Database credentials
vault_database_password: "DatabasePassword456!"
vault_database_root_password: "RootPassword789!"

# API keys
vault_api_key: "your-secret-api-key-here"
vault_github_token: "ghp_your_github_token_here"

# SSL certificates
vault_ssl_cert_password: "CertificatePassword789!"
vault_ssl_private_key: |
  -----BEGIN PRIVATE KEY-----
  your_private_key_content_here
  -----END PRIVATE KEY-----

# Host-specific secrets (if needed)
vault_us01_specific_secret: "US01SpecificSecret"
vault_eu01_specific_secret: "EU01SpecificSecret"
```

#### Host-Specific Vault File (Alternative)

Create `/etc/ansible/inventory/host_vars/us01/vault.yml`:

```yaml
# Encrypted sensitive variables for us01
vault_pgadmin_password: "SuperSecurePassword123!"
vault_pgadmin_email: "admin@company.com"
vault_database_password: "DatabasePassword456!"
vault_api_key: "your-secret-api-key-here"
vault_ssl_cert_password: "CertificatePassword789!"
```

### 3. Referencing Vault Variables

In your regular host_vars file (`/etc/ansible/inventory/host_vars/us01.yml`):

```yaml
# Regular host variables for us01
server_name: "us01"
location: "USA"

# PgAdmin configuration using vault variables
pgadmin:
  container_name: "{{ inventory_hostname|upper }}_PGADMIN"
  image: "dpage/pgadmin4:latest"
  port: "5050"
  network_name: "PW_NET"
  
  # Reference encrypted variables
  default_email: "{{ vault_pgadmin_email }}"
  default_password: "{{ vault_pgadmin_password }}"
  
  # Volume configurations
  data_volume: "/var/lib/perfectwork/{{ inventory_hostname|upper }}/DB/{{ inventory_hostname|upper }}_PGLADMIN"
  servers_config: "/tmp/servers.json"
  
  # Traefik configuration
  traefik:
    enable: "true"
    certresolver: "le_resolver"
    host: "pgadmin.synercatalyst.com"
    service_port: "80"

# Database configuration
database:
  password: "{{ vault_database_password }}"
  
# API configuration
api:
  key: "{{ vault_api_key }}"
```

## Running CStation Commands with Vault

### Method 1: Interactive Password Prompt
```bash
# Deploy with vault password prompt
cstation service docker push docker_pgadmin us01 --ask-vault-pass

# Deploy server configuration with vault
cstation service server push setup us01 --ask-vault-pass
```

### Method 2: Password File

1. **Create a password file** (keep this secure!):
   ```bash
   echo "your_vault_password" > ~/.vault_pass
   chmod 600 ~/.vault_pass
   ```

2. **Use the password file**:
   ```bash
   # Deploy using password file
   cstation service docker push docker_pgladmin us01 --vault-password-file ~/.vault_pass
   
   # Or set environment variable
   export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass
   cstation service docker push docker_pgadmin us01
   ```

### Method 3: Environment Variable
```bash
# Set vault password as environment variable
export ANSIBLE_VAULT_PASSWORD="your_vault_password"
cstation service docker push docker_pgadmin us01
```

## Single vs Multiple Vault Files

### Single Centralized Vault File

**Pros:**
- **Simplicity**: Only one vault password to remember
- **Easier management**: All secrets in one location
- **Reduced complexity**: No need to manage multiple vault files
- **Faster setup**: Quick to implement for small teams
- **Consistent access**: Same vault password works for all deployments

**Cons:**
- **Security risk**: If compromised, all secrets are exposed
- **Access control**: Everyone with vault access can see all secrets
- **Scalability**: Can become unwieldy with many hosts/environments
- **Change management**: Updates affect all environments

**Best for:**
- Small teams (2-5 people)
- Single environment deployments
- Development/testing environments
- Simple infrastructure setups

### Multiple Host-Specific Vault Files

**Pros:**
- **Better security**: Isolated secrets per host/environment
- **Granular access**: Different people can have access to different environments
- **Reduced blast radius**: Compromise affects only specific hosts
- **Scalability**: Easier to manage large infrastructures
- **Environment isolation**: Production secrets separate from development

**Cons:**
- **Complexity**: Multiple passwords to manage
- **More setup**: Requires creating multiple vault files
- **Coordination**: Team needs to manage multiple vault passwords
- **Deployment complexity**: Need to specify correct vault file for each deployment

**Best for:**
- Large teams (5+ people)
- Multiple environments (dev/staging/prod)
- Enterprise deployments
- High-security requirements

### Hybrid Approach

You can also use a combination:
- **Global vault**: Common secrets (API keys, certificates)
- **Environment vaults**: Environment-specific secrets (database passwords)
- **Host vaults**: Host-specific secrets (unique tokens)

```
/etc/ansible/inventory/
├── vault.yml                    # Global secrets
├── group_vars/
│   ├── production/
│   │   └── vault.yml           # Production environment secrets
│   └── development/
│       └── vault.yml           # Development environment secrets
└── host_vars/
    └── critical-server/
        └── vault.yml           # Host-specific secrets
```

## Best Practices

### 1. Vault Password Management
- **Never commit vault passwords to version control**
- Use different vault passwords for different environments
- Store vault passwords securely (password managers, secure key storage)
- Consider using `ansible-vault rekey` to rotate passwords regularly

### 2. File Organization
- Keep vault files separate from regular variable files
- Use consistent naming: `vault.yml` for encrypted files
- Group related secrets together
- Document what each vault variable contains

### 3. Variable Naming Convention
- Prefix vault variables with `vault_` (e.g., `vault_db_password`)
- Use descriptive names that indicate the purpose
- Keep variable names consistent across environments

### 4. Security Considerations
- **Encrypt entire files** rather than individual variables when possible
- **Limit access** to vault files and passwords
- **Use different vault passwords** for different environments (dev/staging/prod)
- **Regularly rotate** sensitive credentials
- **Audit access** to vault files and passwords

## Troubleshooting

### Common Issues

1. **"Decryption failed" error**:
   - Check if you're using the correct vault password
   - Verify the file is actually encrypted with Ansible Vault

2. **"Variable not found" error**:
   - Ensure vault variables are properly referenced in host_vars
   - Check variable naming (case-sensitive)

3. **"Permission denied" error**:
   - Check file permissions on vault files and password files
   - Ensure proper ownership of files

### Debugging Vault Issues

```bash
# Check if a file is encrypted
file /etc/ansible/inventory/host_vars/us01/vault.yml
# Should show: "ASCII text" if encrypted

# View encrypted file content
ansible-vault view /etc/ansible/inventory/host_vars/us01/vault.yml

# Test variable resolution
ansible-inventory -i /etc/ansible/inventory --host us01 --vault-password-file ~/.vault_pass
```

## Integration with CStation

When using vault with cstation commands, the vault password will be passed through to the underlying Ansible commands. This ensures that:

- Encrypted variables are properly decrypted during playbook execution
- Sensitive data remains encrypted at rest
- Multiple hosts can have different encrypted configurations
- Deployment commands work seamlessly with encrypted data

## Example Workflows

### Workflow A: Single Centralized Vault File

1. **Create a single vault file**:
   ```bash
   ansible-vault create /etc/ansible/inventory/vault.yml
   ```

2. **Add all sensitive variables**:
   ```yaml
   # All secrets for all hosts in one file
   vault_pgadmin_password: "SecurePassword123!"
   vault_database_password: "DatabasePassword456!"
   vault_api_key: "your-secret-api-key"
   vault_us01_specific_secret: "US01Secret"
   vault_eu01_specific_secret: "EU01Secret"
   ```

3. **Reference in host_vars files**:
   ```yaml
   # /etc/ansible/inventory/host_vars/us01.yml
   pgadmin:
     default_password: "{{ vault_pgadmin_password }}"
   database:
     password: "{{ vault_database_password }}"
   api:
     key: "{{ vault_api_key }}"
   host_secret: "{{ vault_us01_specific_secret }}"
   ```

4. **Deploy with single vault password**:
   ```bash
   # Same vault password works for all hosts
   cstation service docker push docker_pgadmin us01 --ask-vault-pass
   cstation service docker push docker_pgadmin eu01 --ask-vault-pass
   ```

### Workflow B: Multiple Host-Specific Vault Files

1. **Create vault file for each host**:
   ```bash
   ansible-vault create /etc/ansible/inventory/host_vars/us01/vault.yml
   ansible-vault create /etc/ansible/inventory/host_vars/eu01/vault.yml
   ```

2. **Add host-specific sensitive variables**:
   ```yaml
   # /etc/ansible/inventory/host_vars/us01/vault.yml
   vault_pgadmin_password: "US01_SecurePassword123!"
   vault_database_password: "US01_DatabasePassword456!"
   ```

3. **Reference in host_vars**:
   ```yaml
   # /etc/ansible/inventory/host_vars/us01.yml
   pgadmin:
     default_password: "{{ vault_pgadmin_password }}"
   database:
     password: "{{ vault_database_password }}"
   ```

4. **Deploy with host-specific vault passwords**:
   ```bash
   # Each host may have different vault password
   cstation service docker push docker_pgadmin us01 --ask-vault-pass
   ```

### Quick Start: Single Vault File Setup

For most small teams, here's the quickest way to get started:

```bash
# 1. Create the centralized vault file
ansible-vault create /etc/ansible/inventory/vault.yml

# 2. Add your secrets (editor will open)
# vault_pgadmin_password: "your_password_here"
# vault_database_password: "your_db_password_here"

# 3. Reference in your host_vars files
echo "pgladmin:
  default_password: '{{ vault_pgadmin_password }}'
database:
  password: '{{ vault_database_password }}'" > /etc/ansible/inventory/host_vars/your_host.yml

# 4. Deploy with vault
cstation service docker push docker_pgadmin your_host --ask-vault-pass
```

This approach ensures your sensitive data is encrypted while maintaining the flexibility and ease of use of the cstation CLI tool.