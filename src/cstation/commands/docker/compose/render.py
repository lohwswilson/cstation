from __future__ import annotations

import yaml
from typing import Any


def render_compose(compose_dict: dict[str, Any]) -> str:
    return yaml.dump(compose_dict, sort_keys=False, default_flow_style=False)
