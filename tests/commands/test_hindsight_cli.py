"""
Tests for Hindsight CLI commands (backup, status).
"""

from pathlib import Path
from typer.testing import CliRunner
from cstation.main import app


class _FakeResult:
    def __init__(self, stdout="", exited=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.exited = exited


def _setup_vps(tmp_path: Path):
    vps_dir = tmp_path / "vps" / "sg07"
    vps_dir.mkdir(parents=True)
    (vps_dir / "vps.yaml").write_text("""
apiVersion: cstation/v1
kind: VPS
identity:
  name: sg07
access:
  host: 5.223.74.96
  user: root
  port: 22
""")
    return vps_dir


def test_hindsight_help():
    r = CliRunner().invoke(app, ["hindsight", "--help"])
    assert r.exit_code == 0
    assert "backup" in r.output
    assert "status" in r.output


def test_hindsight_backup_success(monkeypatch, tmp_path: Path):
    vps_dir = _setup_vps(tmp_path)
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()

    executed_cmds = []
    downloaded_files = []

    def mock_run(self, command: str, hide: bool = True, sudo: bool = False):
        executed_cmds.append(command)
        if "ls -1t /root/backups/hindsight_*.dump" in command:
            return _FakeResult(stdout="/root/backups/hindsight_20261022.dump", exited=0)
        if "stat" in command:
            return _FakeResult(stdout="10485760", exited=0)  # 10 MB
        return _FakeResult(stdout="", exited=0)

    def mock_get(self, remote_path: str, local_path: str):
        downloaded_files.append((remote_path, local_path))
        # Create the local file so size and pruning logic work
        Path(local_path).write_bytes(b"dummy dump content")

    monkeypatch.setattr("cstation.ssh.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.ssh.SSHManager.get", mock_get)

    r = CliRunner().invoke(app, ["hindsight", "backup", str(vps_dir), "--dest", str(dest_dir), "--keep", "5"])
    assert r.exit_code == 0
    assert "Found remote dump: /root/backups/hindsight_20261022.dump" in r.output
    assert "Successfully saved:" in r.output
    assert len(downloaded_files) == 1
    assert downloaded_files[0][0] == "/root/backups/hindsight_20261022.dump"
    assert (dest_dir / "hindsight_20261022.dump").exists()


def test_hindsight_backup_default_keep_5_prunes(monkeypatch, tmp_path: Path):
    vps_dir = _setup_vps(tmp_path)
    dest_dir = tmp_path / "backups_prune"
    dest_dir.mkdir()

    # Pre-create 6 existing dummy dumps
    for i in range(6):
        old_dump = dest_dir / f"hindsight_202610{10+i}.dump"
        old_dump.write_bytes(b"old dump")

    def mock_run(self, command: str, hide: bool = True, sudo: bool = False):
        if "ls -1t /root/backups/hindsight_*.dump" in command:
            return _FakeResult(stdout="/root/backups/hindsight_20261022.dump", exited=0)
        if "stat" in command:
            return _FakeResult(stdout="10485760", exited=0)
        return _FakeResult(stdout="", exited=0)

    def mock_get(self, remote_path: str, local_path: str):
        Path(local_path).write_bytes(b"new dump")

    monkeypatch.setattr("cstation.ssh.SSHManager.run", mock_run)
    monkeypatch.setattr("cstation.ssh.SSHManager.get", mock_get)

    # Invoke without specifying --keep (must default to 5)
    r = CliRunner().invoke(app, ["hindsight", "backup", str(vps_dir), "--dest", str(dest_dir)])
    assert r.exit_code == 0
    assert "Pruning 2 older local backup(s) (keeping 5)" in r.output
    remaining = list(dest_dir.glob("hindsight_*.dump"))
    assert len(remaining) == 5


def test_hindsight_status_success(monkeypatch, tmp_path: Path):
    vps_dir = _setup_vps(tmp_path)

    def mock_run(self, command: str, hide: bool = True, sudo: bool = False):
        if "docker ps" in command:
            return _FakeResult(stdout="SG07_HINDSIGHT_SG07DB|Up 17 days|8888, 9999", exited=0)
        if "ls -lh /root/backups" in command:
            return _FakeResult(stdout="-rw-r--r-- 1 root root 42M Oct 22 05:00 /root/backups/hindsight_20261022.dump", exited=0)
        return _FakeResult(stdout="", exited=0)

    monkeypatch.setattr("cstation.ssh.SSHManager.run", mock_run)

    r = CliRunner().invoke(app, ["hindsight", "status", str(vps_dir)])
    assert r.exit_code == 0
    assert "SG07_HINDSIGHT_SG07DB" in r.output
    assert "Up 17 days" in r.output
    assert "42M" in r.output

    r_json = CliRunner().invoke(app, ["hindsight", "status", str(vps_dir), "--output", "json"])
    assert r_json.exit_code == 0
    import json
    data = json.loads(r_json.output)
    assert data["container"] == "SG07_HINDSIGHT_SG07DB"
    assert data["status"] == "Up 17 days"
    assert data["running"] is True
    assert "8888, 9999" in data["ports"]
    assert "42M" in data["latest_backup"]
