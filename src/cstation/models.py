from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class IdentityConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    stage: str = "prod"
    region: str = "manual"
    provider: str = "static"


class AccessConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    host: str
    user: str = "root"
    port: int = 22
    key: Optional[str] = None


class OSBaseline(BaseModel):
    model_config = ConfigDict(extra="allow")
    packages: List[str] = Field(default_factory=list)
    upgrade_all: bool = False
    shell: Optional[str] = None
    terminal: Optional[str] = None
    sshd: Dict[str, Any] = Field(default_factory=dict)
    firewall: Dict[str, Any] = Field(default_factory=dict)
    swap: Dict[str, Any] = Field(default_factory=dict)
    tuning: Dict[str, Any] = Field(default_factory=dict)
    fail2ban: Dict[str, Any] = Field(default_factory=dict)


class OSConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    hostname: Optional[str] = None
    journald: Dict[str, Any] = Field(default_factory=dict)
    baseline: OSBaseline = Field(default_factory=OSBaseline)


class DockerDaemonConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    log_driver: str = "json-file"
    log_opts: Dict[str, str] = Field(default_factory=lambda: {"max-size": "10m", "max-file": "3"})
    storage_driver: Optional[str] = None
    live_restore: bool = True
    iptables: Optional[bool] = None
    default_ulimits: Dict[str, Any] = Field(default_factory=dict)


class DockerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    daemon: DockerDaemonConfig = Field(default_factory=DockerDaemonConfig)
    networks: List[str] = Field(default_factory=lambda: ["PW_NET"])
    directories: List[str] = Field(default_factory=list)


class VPSConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    apiVersion: str = "cstation/v1"
    kind: str = "VPS"
    identity: IdentityConfig
    access: AccessConfig
    os: OSConfig = Field(default_factory=OSConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    facts: Dict[str, Any] = Field(default_factory=dict)


class ContainerConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    apiVersion: str = "cstation/v1"
    kind: str = "Container"
    name: str = ""
    image: Optional[str] = None
    enabled: bool = True
    state: str = "present"
    restart: str = "always"
    restart_policy: Optional[str] = None
    privileged: Optional[bool] = None
    ports: List[str] = Field(default_factory=list)
    volumes: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    env_file: Optional[str] = None
    networks: List[str] = Field(default_factory=list)
    labels: Dict[str, str] = Field(default_factory=dict)
    command: Optional[Union[str, List[str]]] = None
    # Extra fields for orchestration and specialized services
    secrets: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    chmod: Optional[str] = None
    subdirs: List[str] = Field(default_factory=list)
    extra_dirs: List[str] = Field(default_factory=list)
    container_name: Optional[str] = None
    compose_dir: Optional[str] = None
    network: Optional[str] = None
    # Stack-specific fields (for kind: Stack)
    git_repo: Optional[str] = None
    git_branch: Optional[str] = None
    git_dir: Optional[str] = None
    # Service-specific blocks
    odoo_conf: Optional[Dict[str, Any]] = None
    odoo_db: Optional[Any] = None
    traefik: Optional[Dict[str, Any]] = None
    static_config: Optional[Dict[str, Any]] = None


class DockerImageConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    apiVersion: str = "cstation/v1"
    kind: str = "DockerImage"
    name: str
    image: str
    platforms: List[str] = Field(default_factory=lambda: ["linux/amd64", "linux/arm64"])
    build_args: Dict[str, str] = Field(default_factory=dict)


class DNSRecordConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
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
    model_config = ConfigDict(extra="allow")
    apiVersion: str = "cstation/v1"
    kind: str = "DNS"
    domain: str
    records: List[DNSRecordConfig] = Field(default_factory=list)


class GitHubRepoConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
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
    model_config = ConfigDict(extra="allow")
    username: str
    organization: Optional[str] = None
    default_clone_method: str = "ssh"
    default_directory: str = "./repositories"


class GitHubConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    github: GitHubGlobalConfig
    repositories: List[GitHubRepoConfig] = Field(default_factory=list)
