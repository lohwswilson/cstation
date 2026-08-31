from __future__ import annotations

import pytest
from cstation.config import config_manager


@pytest.fixture(autouse=True)
def isolate_cstation_test_env(tmp_path_factory, monkeypatch):
    """
    Ensure every test runs in an isolated environment with a temporary HOME,
    preventing test runs from accessing or modifying ~/.config/cstation.
    """
    test_home = tmp_path_factory.mktemp("cs_home")
    cstation_dir = test_home / ".config" / "cstation"
    cstation_dir.mkdir(parents=True, exist_ok=True)
    (cstation_dir / "vps").mkdir(exist_ok=True)
    (cstation_dir / "dns").mkdir(exist_ok=True)
    (cstation_dir / "images").mkdir(exist_ok=True)

    monkeypatch.setenv("HOME", str(test_home))

    # Reset config_manager state
    config_manager.config_data = {}
    config_manager.config_sources = []
    config_manager.verbose = False
    yield
    config_manager.config_data = {}
    config_manager.config_sources = []
    config_manager.verbose = False
