from __future__ import annotations

from pathlib import Path

import yaml

from cstation.providers.base import VPSStatus
from cstation.providers.static import StaticProvider


def test_static_provider_list_vps_empty_when_no_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))
    p = StaticProvider()
    assert p.list_vps() == []


def test_static_provider_list_vps_skips_non_static(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))
    vps_dir = tmp_path / "cstation" / "vps" / "hetzner-box"
    vps_dir.mkdir(parents=True)
    cfg = vps_dir / "vps.yaml"
    cfg.write_text(
        yaml.dump(
            {
                "apiVersion": "cstation/v1",
                "kind": "VPS",
                "identity": {"name": "hetzner-box", "stage": "prod", "region": "hel1", "provider": "hetzner"},
            }
        ),
        encoding="utf-8",
    )
    p = StaticProvider()
    result = p.list_vps()
    assert result == []


def test_static_provider_list_vps_finds_static_entries(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))
    vps_dir = tmp_path / "cstation" / "vps" / "my-server"
    vps_dir.mkdir(parents=True)
    cfg = vps_dir / "vps.yaml"
    cfg.write_text(
        yaml.dump(
            {
                "apiVersion": "cstation/v1",
                "kind": "VPS",
                "identity": {"name": "my-server", "stage": "prod", "region": "manual", "provider": "static"},
                "access": {"host": "192.168.1.100", "user": "root", "port": 22},
            }
        ),
        encoding="utf-8",
    )
    p = StaticProvider()
    result = p.list_vps()
    assert len(result) == 1
    v = result[0]
    assert v.provider == "static"
    assert v.name == "my-server"
    assert v.ipv4 == "192.168.1.100"
    assert v.status == VPSStatus.RUNNING


def test_static_provider_list_vps_multiple_servers(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))

    for name, host in [("srv1", "10.0.0.1"), ("srv2", "10.0.0.2")]:
        vps_dir = tmp_path / "cstation" / "vps" / name
        vps_dir.mkdir(parents=True)
        cfg = vps_dir / "vps.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "apiVersion": "cstation/v1",
                    "kind": "VPS",
                    "identity": {"name": name, "provider": "static"},
                    "access": {"host": host, "user": "admin", "port": 2222},
                }
            ),
            encoding="utf-8",
        )

    not_static_dir = tmp_path / "cstation" / "vps" / "hetzner-box"
    not_static_dir.mkdir(parents=True)
    (not_static_dir / "vps.yaml").write_text(
        yaml.dump(
            {"apiVersion": "cstation/v1", "kind": "VPS", "identity": {"name": "hetzner-box", "provider": "hetzner"}}
        ),
        encoding="utf-8",
    )

    p = StaticProvider()
    result = p.list_vps()
    assert len(result) == 2
    names = {v.name for v in result}
    assert names == {"srv1", "srv2"}


def test_static_provider_get_vps():
    p = StaticProvider()
    v = p.get_vps(id="1.2.3.4")
    assert v.id == "1.2.3.4"
    assert v.name == "1.2.3.4"
    assert v.ipv4 == "1.2.3.4"
    assert v.provider == "static"
    assert v.status == VPSStatus.RUNNING


def test_static_provider_get_vps_by_name():
    p = StaticProvider()
    v = p.get_vps(name="my-server.com")
    assert v.name == "my-server.com"
    assert v.ipv4 == "my-server.com"


def test_static_provider_cannot_create():
    from cstation.providers.errors import ProviderError

    p = StaticProvider()
    try:
        p.create_vps(name="x", region="y", server_type="z", image="w", ssh_keys=[])
        assert False, "Should have raised"
    except ProviderError:
        pass


def test_static_provider_cannot_delete():
    from cstation.providers.errors import ProviderError

    p = StaticProvider()
    try:
        p.delete_vps(id="1")
        assert False, "Should have raised"
    except ProviderError:
        pass


def test_static_provider_list_vps_ignores_malformed_yaml(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CSTATION_CONFIG_DIR", str(tmp_path / "cstation"))
    vps_dir = tmp_path / "cstation" / "vps" / "bad"
    vps_dir.mkdir(parents=True)
    (vps_dir / "vps.yaml").write_text("not: yaml\nkind: VPS\n", encoding="utf-8")

    good_dir = tmp_path / "cstation" / "vps" / "good"
    good_dir.mkdir(parents=True)
    (good_dir / "vps.yaml").write_text(
        yaml.dump(
            {
                "apiVersion": "cstation/v1",
                "kind": "VPS",
                "identity": {"name": "good", "provider": "static"},
                "access": {"host": "10.0.0.1"},
            }
        ),
        encoding="utf-8",
    )

    not_vps_dir = tmp_path / "cstation" / "vps" / "not-a-vps"
    not_vps_dir.mkdir(parents=True)
    (not_vps_dir / "vps.yaml").write_text(
        yaml.dump({"apiVersion": "cstation/v1", "kind": "Service", "identity": {"name": "not-a-vps"}}),
        encoding="utf-8",
    )

    p = StaticProvider()
    result = p.list_vps()
    assert len(result) == 2
    names = {v.name for v in result}
    assert names == {"bad", "good"}
