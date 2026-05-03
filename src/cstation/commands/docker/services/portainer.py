from __future__ import annotations

from .image_service import ImageService
from .registry import register_service


class PortainerService(ImageService):
    name = "portainer"
    subdirs = ["data"]


register_service("portainer", PortainerService)
