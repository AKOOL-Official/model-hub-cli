"""Assemble verified platform artifacts into a static download site; never publishes."""

import argparse
import hashlib
import re
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("darwin-arm64", "darwin-amd64", "linux-arm64", "linux-amd64")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "artifacts", type=Path, help="Directory containing platform release artifacts"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist/site")
    parser.add_argument("--platforms", nargs="+", choices=PLATFORMS, default=PLATFORMS)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assets = []
    for platform in args.platforms:
        name = f"akool-mh-{platform}"
        candidates = list(args.artifacts.rglob(name))
        if len(candidates) != 1:
            raise SystemExit(f"Expected one {name}; found {len(candidates)}")
        asset = candidates[0]
        expected = asset.with_name(name + ".sha256").read_text().strip()
        with asset.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if (
            not re.fullmatch(r"[a-f0-9]{64}  " + re.escape(name), expected)
            or expected != f"{digest}  {name}"
        ):
            raise SystemExit(f"Artifact checksum mismatch: {name}")
        assets.append((asset, digest))
    release = args.output / "releases" / version
    if release.exists():
        raise SystemExit("Release output already exists; use an empty output directory")
    release.mkdir(parents=True)
    for asset, _ in assets:
        shutil.copy2(asset, release / asset.name)
    (release / "SHA256SUMS").write_text(
        "".join(f"{digest}  {asset.name}\n" for asset, digest in assets)
    )
    shutil.copy2(ROOT / "src/akool_modelhub_cli/install.sh", args.output / "install.sh")
    (args.output / "latest.txt").write_text(version + "\n")
    print(
        f"Static site prepared at {args.output}; upload releases first, then install.sh and latest.txt"
    )


if __name__ == "__main__":
    main()
