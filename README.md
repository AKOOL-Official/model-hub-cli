# AKOOL Model Hub CLI

Command: **`akool-mh`**. Repository: **`model-hub-cli`**. Python package: `akool-modelhub-cli`.
Only the terminal client, installer, tests and release tooling live here. Native binaries
bundle their runtime and versioned Python SDK dependency. Users do not need Git, Python,
Node.js, an SDK checkout or an MCP server.

## Install

Intended production command — **the download site has not been published yet. Do not run
this URL until the operator verifies the first release.**

```bash
curl -fsSL https://maas.akool.com/cli/install.sh | bash
```

The installer detects macOS/Linux and arm64/amd64, verifies the binary's SHA256 and version,
and atomically installs it to `~/.local/bin/akool-mh` without sudo. It prints a PATH
instruction when needed, without editing shell files. Failed downloads or verification
preserve existing installations and credentials. Only macOS arm64 is locally validated;
other targets require native builds and tests before publication.

After publication, pin a version or choose a directory:

```bash
curl -fsSL https://maas.akool.com/cli/install.sh | bash -s -- --version 0.1.0 --install-dir "$HOME/.local/bin"
```

Operators may set `AKOOL_MH_DOWNLOAD_BASE_URL` (HTTPS), `AKOOL_MH_INSTALL_DIR` and
`AKOOL_MH_VERSION`. For release testing use `bash src/akool_modelhub_cli/install.sh
--base-url URL`. Loopback HTTP is supported only for local smoke tests.

## Authenticate and use

```bash
akool-mh login
akool-mh status --json
akool-mh models image --json
akool-mh schema MODEL_ID_FROM_SEARCH --json
akool-mh price MODEL_ID_FROM_SEARCH --input-file input.json --json
akool-mh run MODEL_ID_FROM_SEARCH --input-file input.json --request-id YOUR_UNIQUE_REQUEST_ID --json
akool-mh result YOUR_SAVED_TASK_UUID --wait --timeout 600 --json
akool-mh history --limit 10 --json
```

`login` hides Model Hub API Key entry and saves validated credentials to
`~/.akool/modelhub/config.json`. Main-site Client ID/Secret and `~/.akool/config.json`
remain separate. POSIX directories/files use 0700/0600. `logout` removes only the local key.
API root priority: `--base-url` → `AKOOL_MODELHUB_BASE_URL` → saved configuration →
`https://maas.akool.com/api/v1`. Custom roots include any gateway prefix and `/api/v1`.
CI can set `AKOOL_MODELHUB_API_KEY` and optionally `AKOOL_MODELHUB_BASE_URL`.
Environment keys override local keys. `status` never creates paid tasks.

Model discovery uses the current Key's authorized catalog. Read schemas before filling
`input.json`. Input priority: file → `-p/--prompt` → repeated `-i KEY=VALUE`.
`--input-file -` reads stdin. Model input/output field names are preserved.
`run` submits once and returns; add `--wait` to wait. Media inputs need reachable HTTPS
URLs; local paths and `@file` are not uploaded. Interruption does not cancel backend tasks.
Persist an explicit request ID before submission. `X-Request-Id` becomes `task_uuid`.
On unknown outcomes query that ID or replay identical model/input with the same ID;
never invent a new ID to retry. Automatic submit retries require backend idempotency.

`--json` before or after commands emits one JSON value on stdout; diagnostics use stderr.
Exit codes: 0 success, 1 service/auth/network error, 2 local input/config error,
3 failed/cancelled task, 4 wait deadline, 5 unknown submission outcome, 130 interruption.

## Update

```bash
akool-mh upgrade
akool-mh upgrade --target-version 0.1.0
```

Standalone upgrades use the checksummed download channel and preserve credentials.
They require a published release site. Python installs instead use
`python -m pip install --upgrade akool-modelhub-cli`.

## Develop and release

The SDK is an exact package dependency, never a sibling source path. Before its first
registry release, obtain its wheel as a release artifact:

```bash
uv venv
uv pip install --python .venv/bin/python /path/to/akool_modelhub_sdk-0.1.0-py3-none-any.whl -e . --group dev
.venv/bin/python -m pytest
.venv/bin/ruff check src tests scripts
uv build --out-dir dist
.venv/bin/python scripts/build_binaries.py
```

The native build bundles the installed SDK and runs seven commands against a fake API.
`bash scripts/ci.sh` is the CI entry point; set `MODELHUB_SDK_WHEEL` for the initial
pre-publication build. See [RELEASING.md](RELEASING.md). Builds do not publish or deploy.
