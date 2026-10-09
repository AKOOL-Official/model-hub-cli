<div align="center">

# AKOOL Model Hub CLI

**Discover models. Preview pricing. Run AI tasks from your terminal.**

[![Version: 0.1.0 preview](https://img.shields.io/badge/version-0.1.0_preview-2563eb)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

[Install](#install) · [Quick start](#quick-start) · [Commands](#command-reference) · [Troubleshooting](#troubleshooting)

</div>

`akool-mh` brings AKOOL Model Hub to your terminal, scripts and AI agents. Search the
models available to your API key, inspect their inputs, estimate the price and track
generation tasks. The standalone binary runs without Git, Python or Node.js.

## Install

Install with one command on **macOS or Linux**:

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash
```

Current release: [**v0.1.0**](https://github.com/AKOOL-Official/model-hub-cli/releases/tag/v0.1.0),
with binaries for macOS and Linux on arm64 and amd64.

The installer downloads the matching binary from **GitHub Releases**, verifies its
SHA256 checksum and installs `akool-mh` to `~/.local/bin`. No Git, Python, Node.js or
`sudo` is required. An existing installation is preserved if verification fails.

After installation:

```bash
akool-mh --version
akool-mh login
```

If `~/.local/bin` is not already on your PATH, the installer prints the command to add it.
For the current terminal, run `export PATH="$HOME/.local/bin:$PATH"`; add that line to
`~/.zshrc` or `~/.bashrc` to keep it for new terminals.

<details>
<summary><strong>Platforms and installation options</strong></summary>

The release workflow builds and tests these platforms before publishing:

| Platform | Build and test environment |
| --- | --- |
| macOS · Apple Silicon (arm64) | macOS 14 |
| macOS · Intel (amd64) | macOS 15 |
| Linux · amd64 / arm64 | Ubuntu 22.04, glibc 2.35+ |

Windows and Alpine/musl binaries are not currently provided. macOS binaries are ad-hoc
signed, not Apple notarized.

**Install a specific version:**

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash -s -- --version 0.1.0
```

**Choose an installation directory:**

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash -s -- --install-dir "$HOME/bin"
```

You can also inspect [install.sh](install.sh) before running it, or download a binary
and `SHA256SUMS` directly from [Releases](https://github.com/AKOOL-Official/model-hub-cli/releases).
The installer needs Bash, curl and either `shasum` or `sha256sum`.

</details>

<details>
<summary><strong>Python package alternative</strong></summary>

The standalone installer above is the easiest way to get started. For Python 3.11+
package installations, obtain the CLI wheel and its matching SDK wheel from your
integration contact and place them in the same directory:

```bash
python -m pip install --find-links . ./akool_modelhub_cli-0.1.0-py3-none-any.whl
akool-mh --version
```

The SDK dependency is `akool-modelhub-sdk==0.1.0`; neither Python package is published
to a public package registry yet. You do not need to clone the SDK repository.

</details>

## Quick start

You need a **Model Hub API Key** from your Model Hub account. The main AKOOL service's
Client ID and Client Secret are separate credentials.

### 1. Sign in

```bash
akool-mh login
akool-mh status
```

Paste your API key into the hidden prompt. `login` saves it only after validation;
`status` checks access without creating a generation task. The default API root is
`https://maas.akool.com/api/v1`. If your integration contact supplied a different root,
use `akool-mh login --base-url 'https://YOUR_API_HOST/api/v1'`.

### 2. Choose a model

```bash
akool-mh models image
```

Copy a `model_id` from the results, replace the placeholder below, and inspect its inputs:

```bash
MODEL_ID='MODEL_ID_FROM_SEARCH'
akool-mh schema "$MODEL_ID"
```

Results include only models your key is allowed to use. You can also search with another
keyword or run `akool-mh models` to browse.

### 3. Prepare inputs and preview the price

Create `input.json` using the model's **`input_schema`** and examples. For a model that
accepts `prompt`, a starting file might look like this:

```json
{
  "prompt": "A studio photograph of a ceramic coffee cup on a wooden table"
}
```

Add any other required fields shown by the schema, then check the estimate:

```bash
akool-mh price "$MODEL_ID" --input-file input.json
```

`price` does not generate media. The returned price is an estimate, not a binding charge.
For media inputs, use server-accessible HTTPS URLs; local paths and `@file` do not upload files.

### 4. Submit once

The next command starts a **billable generation task**. Replace `YOUR_UNIQUE_REQUEST_ID`
with a new UUID or unique identifier of at most 36 characters. Save it before submitting:

```bash
REQUEST_ID='YOUR_UNIQUE_REQUEST_ID'
printf '%s\n' "$REQUEST_ID" > request-id.txt
akool-mh run "$MODEL_ID" --input-file input.json --request-id "$REQUEST_ID"
```

`run` returns immediately with a `task_uuid`; the task may still be pending. Keep both
the ID and `input.json` until the task finishes. Use a new request ID for each new generation.

### 5. Get the result

Replace the placeholder with the `task_uuid` returned by `run`:

```bash
TASK_ID='TASK_UUID_FROM_RUN'
akool-mh result "$TASK_ID" --wait --timeout 600
```

Read the task's `status` and `output`; output fields depend on the model. Omit `--wait`
to check once. A timeout or Ctrl-C stops local waiting and **does not cancel the task**.
Run `result` again with the same ID to continue.

## Command reference

| Command | Use it to |
| --- | --- |
| `akool-mh login` | Validate and save your Model Hub API key |
| `akool-mh status` | Check authentication and API connectivity |
| `akool-mh models [query]` | Search the models available to your key |
| `akool-mh schema MODEL_ID` | Inspect input/output schemas and examples |
| `akool-mh price MODEL_ID --input-file input.json` | Estimate the price without generation |
| `akool-mh run MODEL_ID --input-file input.json` | Submit a generation task; add `--wait` to wait |
| `akool-mh result TASK_ID` | Read an existing task; add `--wait` to keep waiting |
| `akool-mh history --limit 10` | List account task history across API keys |
| `akool-mh logout` | Remove the locally saved key |
| `akool-mh upgrade` | Update a standalone binary from GitHub Releases |

Every command accepts `--help`. Use `akool-mh --version` to check your installed version.

<details>
<summary><strong>Input shortcuts and global options</strong></summary>

Use a JSON file for repeatable requests, or supply individual fields when they match the
selected model's schema. These examples only preview the price:

```bash
akool-mh price "$MODEL_ID" -p 'A studio photograph of a ceramic cup'
akool-mh price "$MODEL_ID" --input-file input.json -i 'prompt="A red ceramic cup"'
cat input.json | akool-mh price "$MODEL_ID" --input-file -
```

Input precedence is **JSON file → `-p/--prompt` → repeated `-i KEY=VALUE`**; later sources
override earlier fields. `-i` parses valid JSON values and otherwise treats them as strings.
Field names must match the model's schema exactly.

| Option | Behavior |
| --- | --- |
| `--json` | Emit one compact JSON value on stdout; works before or after the command |
| `--base-url URL` | Override the API root, including any gateway prefix and `/api/v1` |
| `--request-timeout SECONDS` | Limit each HTTP operation; default: 90 seconds |
| `--timeout SECONDS` | Limit waiting with `run --wait` or `result --wait`; default: 600 seconds |

</details>

## Scripts and CI

Provide `AKOOL_MODELHUB_API_KEY` through your CI secret store or environment instead of
interactive login. To use a custom API root, also set `AKOOL_MODELHUB_BASE_URL`.

```bash
# AKOOL_MODELHUB_API_KEY is already supplied by your environment.
akool-mh status --json
akool-mh models image --json
akool-mh history --limit 10 --json > history.json
```

With `--json`, stdout contains one JSON result; diagnostics and task-ID notices go to stderr.
Check the exit code as well as task `status`: a successful submission can still be pending.

<details>
<summary><strong>Exit codes</strong></summary>

| Code | Meaning | Next step |
| --- | --- | --- |
| `0` | Command succeeded | For a submitted task, check its status |
| `1` | Service, authentication or network error | Check the error message and connection |
| `2` | Invalid local input or configuration | Check arguments, JSON and model schema |
| `3` | Task failed or was cancelled | Inspect the task error |
| `4` | Waiting deadline expired | Query or wait for the same task again |
| `5` | Submission outcome is unknown | Recover the original request ID; see below |
| `130` | Interrupted locally | Query the original task if already submitted |

</details>

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `akool-mh: command not found` | Add `~/.local/bin` to `PATH`; see [installation](#install) |
| Installer URL returns a web page | Use the `raw.githubusercontent.com` command above, not a GitHub `/blob/` page |
| No downloadable release found | Check [Releases](https://github.com/AKOOL-Official/model-hub-cli/releases) and your connection to GitHub |
| `401` / authentication failed | Check that you are using a valid Model Hub API Key and the correct API root |
| `403` / access denied | Check the key's permissions and IP restrictions |
| Model missing or `404` | Search with `models` using the same key and check the exact model ID |
| Invalid input / `400` / `422` | Read `schema` again and correct required fields, types and allowed values |
| `429` / rate limited | Respect the response's retry interval before trying again |
| Waiting timed out | Run `result TASK_ID --wait` again; the backend task continues |

### Recover an interrupted submission

If `run` reports an unknown outcome, **query the original request ID before submitting
anything new**. It is also the task ID used for recovery:

```bash
REQUEST_ID="$(cat request-id.txt)"
akool-mh result "$REQUEST_ID" --wait --timeout 600
```

If replay is needed, use the **same request ID, model and unchanged input**. A fresh ID
creates a new generation and may incur another charge. Automatic submission retries are
enabled only when the backend advertises request-ID idempotency.

<details>
<summary><strong>Credentials and configuration</strong></summary>

- Local login file: `~/.akool/modelhub/config.json`.
- The environment key overrides the saved key. `logout` removes only the saved key;
  unset `AKOOL_MODELHUB_API_KEY` separately if it remains active.
- API root priority: `--base-url` → `AKOOL_MODELHUB_BASE_URL` → saved configuration →
  `https://maas.akool.com/api/v1`.
- Main-site `akool-cli` credentials in `~/.akool/config.json` are separate.
- Keep API keys out of prompts, input JSON and issue reports.

</details>

## Updates

Update a standalone installation from GitHub Releases:

```bash
akool-mh upgrade
```

Use `akool-mh upgrade --target-version VERSION` to select a specific published version.
Updates preserve local credentials and install into the existing binary’s directory.

Python package installations use pip rather than `upgrade`: install the supplied newer
wheel with its matching SDK dependency, or use `python -m pip install --upgrade
akool-modelhub-cli` after registry publication.

## Support and development

For bugs or feature requests, [open an issue](https://github.com/AKOOL-Official/model-hub-cli/issues)
with your CLI version, operating system and the error message. Remove credentials and
private input before posting.

Integrating from application code? Use the official
[Python SDK](https://github.com/AKOOL-Official/model-hub-sdk-python) or
[TypeScript SDK](https://github.com/AKOOL-Official/model-hub-sdk-typescript).

<details>
<summary><strong>Build from source and contribute</strong></summary>

Development requires Python 3.11+ and `uv`. Before the SDK is published, obtain its exact
wheel release artifact. From this repository's root:

```bash
uv venv
uv pip install --python .venv/bin/python /path/to/akool_modelhub_sdk-0.1.0-py3-none-any.whl . --group dev
.venv/bin/python -m pytest
.venv/bin/ruff check src tests scripts
uv build --out-dir dist
.venv/bin/python scripts/build_binaries.py
```

The native build bundles its SDK dependency and runtime, then checks seven commands
against a fake local API. It does not call a real model or publish artifacts.
See [CI.md](CI.md) for the CI entry point and [RELEASING.md](RELEASING.md) for native
build targets and the release process.

</details>

## License

[MIT](LICENSE) · Copyright (c) 2026 AKOOL.
