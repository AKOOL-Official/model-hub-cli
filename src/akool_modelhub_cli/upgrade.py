"""Update a standalone installation using its bundled, checksum-verifying installer."""

import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from akool_modelhub_sdk import ModelHubError


def upgrade_binary(*, version: str | None = None) -> dict:
    if not getattr(sys, "frozen", False):
        raise ValueError(
            "upgrade requires the standalone binary. For a Python installation use "
            "python -m pip install --upgrade akool-modelhub-cli"
        )
    if os.name != "posix":
        raise ValueError("Standalone upgrades currently support macOS and Linux")
    executable = Path(sys.executable).absolute()
    script = files("akool_modelhub_cli").joinpath("install.sh").read_text()
    args = ["bash", "-s", "--", "--install-dir", str(executable.parent)]
    if version:
        args.extend(["--version", version])
    try:
        result = subprocess.run(args, input=script, text=True, capture_output=True, timeout=1200)
    except subprocess.TimeoutExpired as exc:
        raise ModelHubError("Upgrade timed out; retry the installer") from exc
    if result.returncode:
        raise ModelHubError(result.stderr.strip() or "Upgrade failed; retry the installer")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return {"updated": True, "path": str(executable), "message": result.stdout.strip()}
