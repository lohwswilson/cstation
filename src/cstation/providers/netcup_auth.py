from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://www.servercontrolpanel.de"
AUTH_URL = f"{BASE_URL}/realms/scp/protocol/openid-connect"
API_BASE_URL = f"{BASE_URL}/scp-core/api/v1"
CLIENT_ID = "scp"
SCOPE = "offline_access openid"

CREDENTIALS_DIR = Path.home() / ".config" / "cstation"
CREDENTIALS_FILE = CREDENTIALS_DIR / "netcup-oauth.json"


class NetcupAuthError(Exception):
    pass


def _url_post(url: str, data: dict[str, str]) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            detail = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            detail = {"raw": body}
        raise NetcupAuthError(
            f"HTTP {e.code} from {url}: {detail}"
        ) from e
    except urllib.error.URLError as e:
        raise NetcupAuthError(f"Network error contacting {url}: {e.reason}") from e


def request_device_code() -> dict[str, Any]:
    return _url_post(
        f"{AUTH_URL}/auth/device",
        {"client_id": CLIENT_ID, "scope": SCOPE},
    )


def exchange_device_code(device_code: str) -> dict[str, Any]:
    return _url_post(
        f"{AUTH_URL}/token",
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": CLIENT_ID,
        },
    )


def wait_for_device_authorization(
    device_code: str,
    interval: int = 5,
    expires_in: int = 600,
) -> dict[str, Any]:
    deadline = time.monotonic() + expires_in
    current_interval = interval
    while time.monotonic() < deadline:
        try:
            return exchange_device_code(device_code)
        except NetcupAuthError as e:
            msg = str(e).lower()
            if "authorization_pending" in msg:
                time.sleep(current_interval)
                continue
            if "slow_down" in msg:
                current_interval = min(current_interval + 5, 60)
                time.sleep(current_interval)
                continue
            if "access_denied" in msg:
                raise NetcupAuthError("Access denied on device authorization.") from e
            if "expired_token" in msg:
                raise NetcupAuthError("Device code expired. Please run login again.") from e
            raise
    raise NetcupAuthError("Device authorization timed out.")


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    return _url_post(
        f"{AUTH_URL}/token",
        {
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )


def revoke_refresh_token(refresh_token: str) -> None:
    try:
        _url_post(
            f"{AUTH_URL}/revoke",
            {
                "client_id": CLIENT_ID,
                "token": refresh_token,
                "token_type_hint": "refresh_token",
            },
        )
    except NetcupAuthError:
        pass


def load_credentials() -> dict[str, Any]:
    if not CREDENTIALS_FILE.exists():
        raise NetcupAuthError(
            "No stored Netcup credentials. Run: cstation netcup auth login"
        )
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise NetcupAuthError(f"Invalid credentials file: {e}") from e
    if not data.get("refresh_token"):
        raise NetcupAuthError("Credentials file missing refresh_token. Run: cstation netcup auth login")
    return data


def save_credentials(refresh_token: str) -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(
        json.dumps({"refresh_token": refresh_token}, indent=2),
        encoding="utf-8",
    )
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except OSError:
        pass


def delete_credentials() -> None:
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


def credentials_exist() -> bool:
    return CREDENTIALS_FILE.exists()


def get_access_token() -> str:
    creds = load_credentials()
    result = refresh_access_token(creds["refresh_token"])
    new_refresh = result.get("refresh_token")
    if new_refresh:
        save_credentials(new_refresh)
    return result["access_token"]