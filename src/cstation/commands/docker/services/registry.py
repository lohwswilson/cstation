from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ContainerService

_SERVICE_CLASSES: dict[str, type[ContainerService]] = {}


def register_service(name: str, cls: type[ContainerService]) -> None:
    _SERVICE_CLASSES[name] = cls


def get_service(name: str) -> type[ContainerService]:
    if name not in _SERVICE_CLASSES:
        raise ValueError(f"Unknown service: {name}. Available: {', '.join(available_services())}")
    return _SERVICE_CLASSES[name]


def available_services() -> list[str]:
    return sorted(_SERVICE_CLASSES.keys())
