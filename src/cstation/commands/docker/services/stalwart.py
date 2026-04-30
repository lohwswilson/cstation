from __future__ import annotations

from .registry import register_service
from .image_service import ImageService


class StalwartService(ImageService):
    name = "stalwart"
    subdirs = ["etc", "data"]


register_service("stalwart", StalwartService)