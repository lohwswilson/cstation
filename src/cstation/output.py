"""
Output formatting utilities for CStation CLI.
Supports table (human-readable), json, and yaml output formats.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable, Optional
import yaml
from rich.console import Console

console = Console()


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


def print_formatted(
    data: Any,
    format_type: OutputFormat | str = OutputFormat.TABLE,
    table_renderer: Optional[Callable[[], None]] = None,
) -> None:
    """
    Print data according to the selected format.

    If format is TABLE and a table_renderer callback is provided, table_renderer is executed.
    If format is JSON, data is dumped as formatted JSON.
    If format is YAML, data is dumped as formatted YAML.
    """
    fmt = OutputFormat(format_type) if isinstance(format_type, str) else format_type

    if fmt == OutputFormat.JSON:
        print(json.dumps(data, indent=2, default=str))
    elif fmt == OutputFormat.YAML:
        print(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    else:
        if table_renderer is not None:
            table_renderer()
        else:
            console.print(data)
