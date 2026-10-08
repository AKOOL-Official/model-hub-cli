# Independent CI entry point

Run `bash scripts/ci.sh` from a clean checkout. No sibling source repository is needed.
The script installs development dependencies, runs checks and builds release artifacts;
it never uploads packages or deploys a service. The repository is hosted under `AKOOL-Official` on GitHub.
GitHub Actions is not yet configured; this script is the portable CI entry point. Each repository has independent version tags.

Python projects require Python 3.11+ and uv (CI defaults to Python 3.12).
CLI and MCP use the exact SDK version in pyproject.toml. Before registry publication,
set `MODELHUB_SDK_WHEEL` to an absolute path of its downloaded wheel release artifact.
Once published, the normal package index resolves it. Never use a sibling editable SDK.
Run the native build on macOS arm64/amd64 and Linux arm64/amd64; see RELEASING.md.
