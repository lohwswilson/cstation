# Contributing to CStation 🤝

Thank you for contributing to **CStation**! This document provides guidelines and conventions for developing, testing, and adding features to the codebase.

---

## 🛠️ Development Setup

CStation requires **Python 3.13** and uses [**`uv`**](https://docs.astral.sh/uv/) for high-speed package management.

### 1. Environment Installation

```bash
# Clone the repository
git clone https://github.com/lohwswilson/cstation.git
cd cstation

# Create virtual environment and install with test extras
uv pip install -e ".[test]"

# Verify development CLI
uv run cstation --help
```

---

## 🧪 Testing Guidelines

CStation has an extensive automated test suite with **244+ unit and integration tests**. All tests must pass before submitting code.

### Running Tests

```bash
# Run all tests
uv run pytest -q

# Run single test module
uv run pytest -q tests/commands/test_docker_cli.py

# Run specific test function
uv run pytest -q tests/commands/test_docker_cli.py::test_docker_apply_traefik
```

### Writing Tests with Mock SSH

When writing tests for commands that interact with remote VPS hosts over SSH, use the `_mock_ssh_run` fixture to avoid real network calls:

```python
def test_my_feature(tmp_path, monkeypatch):
    class MockResult:
        def __init__(self, stdout="", exited=0):
            self.stdout = stdout
            self.stderr = ""
            self.exited = exited

    def mock_run(self, command, hide=True, sudo=False):
        if "docker info" in command:
            return MockResult(stdout="ok")
        if "docker compose version" in command:
            return MockResult(stdout="ok")
        return MockResult(stdout="")

    monkeypatch.setattr("cstation.commands.docker.main.SSHManager.run", mock_run)
    # Invoke command and assert
```

---

## 🏗️ Adding a New Command Group

To add a new command group to CStation:

1. **Create the Command Module**:
   Create `src/cstation/commands/<group>/main.py` exporting a `typer.Typer` instance:
   ```python
   import typer

   my_app = typer.Typer(name="mycommand", help="My command group description")

   @my_app.command("status")
   def status():
       typer.echo("Status OK")
   ```

2. **Register in Root Entry Point**:
   In `src/cstation/main.py`, import and add the Typer app:
   ```python
   from .commands.mycommand.main import my_app
   app.add_typer(my_app)
   ```

3. **Add Tests**:
   Add corresponding test cases in `tests/commands/test_mycommand_cli.py`.

---

## 📝 Code Conventions

- **Python 3.13 Idioms**: Use standard generic types (`list[str]`, `dict[str, Any]`, `str | None`).
- **Pydantic V2 Models**: All configuration schemas in `src/cstation/models.py` must use Pydantic V2 models with strict type validation. Catch `ValidationError` at load boundaries and format errors with clear field paths.
- **SSH Roundtrips**: Never run multiple single SSH commands in loops when collecting data. Use `SSHManager.run_batch()` to bundle commands into a single roundtrip.
- **Idempotent Apply**: Every mutating command should accept a `dry_run: bool` flag and support an interactive `plan` mode.
- **Secrets Isolation**: Never hardcode secrets in YAML fragments or commit them to source control.

---

## 📦 Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-new-feature`
2. Implement your changes and ensure all tests pass: `uv run pytest -q`
3. Commit with descriptive commit messages.
4. Push your branch and open a Pull Request.
