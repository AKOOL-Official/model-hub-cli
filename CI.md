# Build and release CI

[`.github/workflows/release.yml`](.github/workflows/release.yml) runs on pull requests,
version tags and manual dispatch. It builds a pinned Python SDK wheel, then tests and
builds native CLI binaries on macOS arm64/amd64 and Linux arm64/amd64.

Each native job verifies the CLI's seven commands plus installation, self-upgrade,
failed-upgrade preservation and unchanged credentials. Checks use only a local fake API.
Artifacts are retained for 14 days. Actions are pinned to immutable revisions.

Only a pushed `vVERSION` tag matching `pyproject.toml` publishes a GitHub Release, and
only after all four platform jobs pass. Build jobs have read-only repository access;
the final publish job alone has `contents: write`. See [RELEASING.md](RELEASING.md).

For local package checks, run `bash scripts/ci.sh`. It requires Python 3.11+ and uv
(defaults to Python 3.12), installs the CLI as a package, tests it and builds its wheel.
Before the SDK's first registry release, set `MODELHUB_SDK_WHEEL` to the absolute path
of the matching wheel. This local entry point never publishes or deploys anything.
