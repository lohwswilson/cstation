# Portainer Setup Guide

Portainer is a lightweight management UI for Docker environments. This guide will help you deploy Portainer using CStation.

## Prerequisites

- CStation installed and configured
- Target server added to inventory
- Docker installed on target server
- SSH access to target server

## Deployment

### Step 1: List Available Profiles

First, verify that the Portainer profile is available:

```bash
cstation service docker ls
```

You should see `portainer` in the list of available profiles.

### Step 2: Deploy Portainer

Deploy Portainer to your target server:

```bash
cstation service docker push portainer <target_host>
```

**Example:**
```bash
# Deploy to eu01 server
cstation service docker push portainer eu01
```

### Step 3: Access Portainer

Once deployed, Portainer will be available at:
- **HTTP:** `http://<server_ip>:9000`
- **HTTPS:** `https://<server_ip>:9443` (if SSL is configured)

## Initial Setup

1. Open your browser and navigate to the Portainer URL
2. Create an admin user account
3. Choose "Docker" as the environment type
4. Connect to the local Docker environment

## Features

- **Container Management:** Start, stop, restart, and remove containers
- **Image Management:** Pull, build, and manage Docker images
- **Network Management:** Create and manage Docker networks
- **Volume Management:** Manage Docker volumes and bind mounts
- **Stack Deployment:** Deploy multi-container applications using Docker Compose
- **User Management:** Role-based access control

## Troubleshooting

### Portainer Not Accessible

1. Check if the container is running:
   ```bash
   docker ps | grep portainer
   ```

2. Verify port accessibility:
   ```bash
   netstat -tlnp | grep :9000
   ```

3. Check firewall settings:
   ```bash
   sudo ufw status
   ```

### Container Won't Start

1. Check Docker logs:
   ```bash
   docker logs portainer
   ```

2. Verify Docker socket permissions:
   ```bash
   ls -la /var/run/docker.sock
   ```

## Security Considerations

- Change default admin password immediately
- Enable HTTPS in production environments
- Restrict network access using firewall rules
- Regularly update Portainer to the latest version
- Use strong authentication methods

## Advanced Configuration

For advanced configuration options, modify the Portainer Ansible playbook located at:
`/etc/cstation/service/docker/portainer.yml`

Common customizations include:
- SSL certificate configuration
- Custom port mappings
- Volume mount configurations
- Environment variables

## Related Services

### Portainer Agent

For managing remote Docker hosts from this Portainer instance, consider deploying Portainer Agent on remote servers:

- [Portainer Agent Setup Guide](PORTAINER_AGENT_SETUP_GUIDE.md) - Deploy lightweight agents for remote management
- Command: `cstation service docker push portainer_agent <remote_host>`

### Service Architecture

**Centralized Management Setup:**
```
[This Server]           [Remote Servers]
Portainer UI        --> Portainer Agent (Server 1)
(Port 9000)         --> Portainer Agent (Server 2)
                    --> Portainer Agent (Server N)
```

## Related Documentation

- [Docker Service Management](../commands/docker.md) - General Docker service deployment
- [Services Overview](../services/README.md) - All available Docker services
- [Server Management](../commands/server.md) - Managing target servers