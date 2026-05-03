from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, IPvAnyAddress

class IdentityConfig(BaseModel):
    name: str
    stage: str = "prod"
    region: str = "manual"
    provider: str = "static"

class AccessConfig(BaseModel):
    host: str
    user: str = "root"
    port: int = 22
    key: Optional[str] = None

class OSBaseline(BaseModel):
    packages: List[str] = Field(default_factory=list)
    sshd: Dict[str, Any] = Field(default_factory=dict)
    firewall: Dict[str, Any] = Field(default_factory=dict)

class OSConfig(BaseModel):
    baseline: OSBaseline = Field(default_factory=OSBaseline)

class DockerDaemonConfig(BaseModel):
    log_driver: str = "json-file"
    log_opts: Dict[str, str] = Field(default_factory=lambda: {"max-size": "10m", "max-file": "3"})

class DockerConfig(BaseModel):
    daemon: DockerDaemonConfig = Field(default_factory=DockerDaemonConfig)
    networks: List[str] = Field(default_factory=lambda: ["PW_NET"])

class VPSConfig(BaseModel):
    apiVersion: str = "cstation/v1"
    kind: str = "VPS"
    identity: IdentityConfig
    access: AccessConfig
    os: OSConfig = Field(default_factory=OSConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    facts: Dict[str, Any] = Field(default_factory=dict)

class ContainerConfig(BaseModel):
    apiVersion: str = "cstation/v1"
    kind: str = "Container"
    name: str
    image: str
    enabled: bool = True
    state: str = "present"
    restart: str = "always"
    ports: List[str] = Field(default_factory=list)
    volumes: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    networks: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    command: Optional[str | List[str]] = None
    # Extra fields for orchestration and specialized services
    secrets: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    chmod: Optional[str] = None
    subdirs: List[str] = Field(default_factory=list)
    extra_dirs: List[str] = Field(default_factory=list)
    container_name: Optional[str] = None
    network: Optional[str] = None
    # Service-specific blocks
    odoo_conf: Optional[Dict[str, Any]] = None
    odoo_db: Optional[Any] = None
    traefik: Optional[Dict[str, Any]] = None
    static_config: Optional[Dict[str, Any]] = None
    # Internal fields (prefixed with _) are ignored by validation if not defined,
    # but we can use model_extra if we set extra='allow'
    class Config:
        extra = "allow"

class DNSRecordConfig(BaseModel):
    name: str = "@"
    type: str
    value: str
    ttl: int = 1
    priority: Optional[int] = None
    proxied: bool = False
    comment: str = "cstation"
    srv_weight: Optional[int] = None
    srv_port: Optional[int] = None

class DNSConfig(BaseModel):
    apiVersion: str = "cstation/v1"
    kind: str = "DNS"
    domain: str
    records: List[DNSRecordConfig] = Field(default_factory=list)

class GitHubRepoConfig(BaseModel):
    name: str
    description: str = ""
    branch: str = "main"
    category: str = "default"
    clone_method: str = "ssh"
    auto_sync: bool = False
    local_path: str
    url: Optional[str] = None
    fork_url: Optional[str] = None
    upstream_url: Optional[str] = None
    includes: List[str] = Field(default_factory=list)

class GitHubGlobalConfig(BaseModel):
    username: str
    organization: Optional[str] = None
    default_clone_method: str = "ssh"
    default_directory: str = "./repositories"

class GitHubConfig(BaseModel):
    github: GitHubGlobalConfig
    repositories: List[GitHubRepoConfig] = Field(default_factory=list)
