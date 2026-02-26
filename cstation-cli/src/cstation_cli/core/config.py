from pathlib import Path
import yaml
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Host(BaseModel):
    name: str
    host: str
    user: str = "root"
    port: int = 22
    groups: List[str] = ["default"]
    vars: Dict[str, str] = {}

class Inventory(BaseModel):
    hosts: List[Host] = []
    
    def get_hosts_by_group(self, group_name: str) -> List[Host]:
        if group_name == "all":
            return self.hosts
        return [h for h in self.hosts if group_name in h.groups]

    def get_all_groups(self) -> List[str]:
        groups = set()
        for h in self.hosts:
            groups.update(h.groups)
        return sorted(list(groups))

class Config(BaseModel):
    inventory: Inventory = Inventory()
    stacks_path: str = "./stacks"
    
    @classmethod
    def load(cls, path: Path):
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return cls(**data)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, sort_keys=False)

def get_config_path() -> Path:
    return Path.home() / ".config" / "cstation-cli" / "config.yaml"

def resolve_host(name: str) -> Host:
    """Helper to find a host in the inventory or return a transient Host object if not found."""
    config = Config.load(get_config_path())
    for h in config.inventory.hosts:
        if h.name == name:
            return h
    # Fallback to assuming the name IS the host IP/FQDN
    return Host(name=name, host=name)
