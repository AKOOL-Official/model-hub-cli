"""Build a native CLI release from the installed, versioned SDK dependency."""

import hashlib
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os_name = platform.system().lower()
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "AMD64": "amd64"}.get(
        platform.machine()
    )
    if os_name not in ("darwin", "linux") or arch is None:
        raise SystemExit("Build on macOS/Linux arm64 or amd64")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    binary_dir = ROOT / "dist" / f"{os_name}-{arch}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "akool-mh",
            "--distpath",
            str(binary_dir),
            "--workpath",
            str(ROOT / "build"),
            "--specpath",
            str(ROOT / "build"),
            "--collect-data",
            "jsonschema_specifications",
            "--collect-data",
            "akool_modelhub_cli",
            str(ROOT / "scripts/cli_entry.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    binary = binary_dir / "akool-mh"
    reported = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if reported != f"AKOOL Model Hub CLI {version}":
        raise SystemExit("Package and binary versions do not match")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/smoke_binaries.py"), str(binary_dir)], check=True
    )
    release = ROOT / "dist" / "release" / version
    release.mkdir(parents=True, exist_ok=True)
    asset = release / f"akool-mh-{os_name}-{arch}"
    shutil.copy2(binary, asset)
    digest = hashlib.file_digest(asset.open("rb"), "sha256").hexdigest()
    (release / f"{asset.name}.sha256").write_text(f"{digest}  {asset.name}\n")
    print(f"Built and smoke-tested {asset}")


if __name__ == "__main__":
    main()
