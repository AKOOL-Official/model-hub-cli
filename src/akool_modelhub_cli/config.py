"""Local credentials owned exclusively by the terminal client."""

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

MAX_CONFIG_BYTES = 65536
DEFAULT_BASE_URL = "https://maas.akool.com/api/v1"


@dataclass(frozen=True)
class Configuration:
    api_key: str = field(repr=False)
    base_url: str
    credential_source: str


def config_path() -> Path:
    return Path.home() / ".akool" / "modelhub" / "config.json"


def validate_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in ("http", "https")
        or (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"))
    ):
        raise ValueError(
            "Use an HTTPS API root without credentials, query or fragment (HTTP is allowed for localhost)."
        )
    return value


def read_config(path: Path | None = None) -> dict[str, str]:
    path = path or config_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Credential configuration must not be a symlink")
    try:
        with path.open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Credential configuration must be a regular file")
            data = source.read(MAX_CONFIG_BYTES + 1)
    except FileNotFoundError:
        return {}
    if len(data) > MAX_CONFIG_BYTES:
        raise ValueError("Credential configuration is too large")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid credential configuration JSON") from exc
    if not isinstance(result, dict) or any(
        not isinstance(result[key], str) for key in ("api_key", "base_url") if key in result
    ):
        raise ValueError("Invalid credential configuration fields")
    return {key: result[key] for key in ("api_key", "base_url") if key in result}


def resolve_config(*, base_url: str | None = None, path: Path | None = None) -> Configuration:
    # Environment-only deployments must work without touching local credentials.
    key = os.getenv("AKOOL_MODELHUB_API_KEY")
    base = base_url or os.getenv("AKOOL_MODELHUB_BASE_URL")
    source = "environment" if key else "local_config"
    saved = read_config(path) if not key or not base else {}
    key = key or saved.get("api_key")
    base = base or saved.get("base_url") or DEFAULT_BASE_URL
    if not key or not base:
        raise ValueError(
            "Run akool-mh login or set AKOOL_MODELHUB_API_KEY and AKOOL_MODELHUB_BASE_URL"
        )
    if not key.strip() or any(c in key for c in "\r\n"):
        raise ValueError("Invalid API key format")
    return Configuration(key, validate_base_url(base), source)


def write_config(values: dict[str, str], path: Path | None = None) -> None:
    path = path or config_path()
    # Never modify AKOOL's main config or follow product configuration symlinks.
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise ValueError("Credential configuration must not be a symlink")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as target:
            json.dump(values, target)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def clear_credentials(path: Path | None = None) -> None:
    values = read_config(path)
    if "api_key" in values:
        values.pop("api_key")
        write_config(values, path)
