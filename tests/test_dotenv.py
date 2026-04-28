from __future__ import annotations

from pathlib import Path

import cstation.config as config


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_dotenv_project_overrides_system(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    workdir = project / "subdir"

    _write(project / "pyproject.toml", "[project]\nname='x'\n")
    _write(project / ".env", "HETZNER_TOKEN=project\n")
    _write(home / ".config" / "cstation" / ".env", "HETZNER_TOKEN=system\n")
    workdir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("HETZNER_TOKEN", raising=False)

    config.load_dotenv()

    assert config.os.getenv("HETZNER_TOKEN") == "project"


def test_dotenv_does_not_override_exported_env(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    workdir = project

    _write(project / "pyproject.toml", "[project]\nname='x'\n")
    _write(project / ".env", "HETZNER_TOKEN=project\n")
    _write(home / ".config" / "cstation" / ".env", "HETZNER_TOKEN=system\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HETZNER_TOKEN", "exported")
    monkeypatch.chdir(workdir)

    config.load_dotenv()

    assert config.os.getenv("HETZNER_TOKEN") == "exported"


def test_dotenv_parses_quoted_values(monkeypatch, tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "project"

    _write(project / "pyproject.toml", "[project]\nname='x'\n")
    _write(project / ".env", 'SOME_VALUE="hello world"\n')
    _write(home / ".config" / "cstation" / ".env", "")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("SOME_VALUE", raising=False)
    monkeypatch.chdir(project)

    config.load_dotenv()

    assert config.os.getenv("SOME_VALUE") == "hello world"


def test_ansible_setup_is_skipped_when_no_ansible_cfg(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANSIBLE_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    config.get_config().setup_ansible_environment()
    assert config.os.getenv("ANSIBLE_CONFIG") is None
