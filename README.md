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

> [!IMPORTANT]
> **Preview release — public downloads are not available yet.** Request the macOS
> Apple Silicon preview binary from your AKOOL integration contact. The hosted installer
> is not live, and there are no downloadable GitHub Releases yet.

## Install

### macOS Apple Silicon preview

Obtain **`akool-mh-darwin-arm64`** and **`akool-mh-darwin-arm64.sha256`** from your
integration contact. In the directory containing both files, run:

```bash
shasum -a 256 -c akool-mh-darwin-arm64.sha256 && \
  mkdir -p "$HOME/.local/bin" && \
  install -m 755 ./akool-mh-darwin-arm64 "$HOME/.local/bin/akool-mh"
```

Then make the command available in your current terminal and check the version:

```bash
export PATH="$HOME/.local/bin:$PATH"
akool-mh --version
```

If needed, add the same `export PATH` line to `~/.zshrc` or `~/.bashrc` so it also works
in new terminals. Installation does not require `sudo`.

<details>
<summary><strong>Other platforms and Python installations</strong></summary>

| Platform | Current status |
| --- | --- |
| macOS · Apple Silicon (arm64) | Preview binary validated locally |
| macOS · Intel (amd64) | Native build and validation pending |
| Linux · arm64 / amd64 | Native builds and validation pending |
| Windows | No standalone installer currently provided |

**Python 3.11+ alternative:** obtain the CLI wheel and matching Python SDK wheel from
your integration contact. Place both files in the same directory, then run:

```bash
python -m pip install --find-links . ./akool_modelhub_cli-0.1.0-py3-none-any.whl
akool-mh --version
```

The matching dependency is `akool-modelhub-sdk==0.1.0`. You do not need to clone the SDK
repository. Neither package is published to a public package registry yet.

</details>

<details>
<summary><strong>Planned one-command installer — not available yet</strong></summary>

After the download service launches, the installation command will be:

```bash
# Not live yet — do not run until public downloads are announced.
curl -fsSL https://maas.akool.com/cli/install.sh | bash
```

The installer will select the matching platform binary, verify its checksum and install
it to `~/.local/bin`. It supports `--version` and `--install-dir`, and preserves an
existing installation if downloading or verification fails.

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
| `akool-mh upgrade` | Update a standalone binary once public downloads are available |

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
| Installer URL returns a web page | Public downloads are not live yet; obtain preview artifacts from your integration contact |
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

Once public downloads are available, standalone installations can update with:

```bash
akool-mh upgrade
```

Use `akool-mh upgrade --target-version VERSION` to select a specific published version.
Updates preserve local credentials. Until the download service launches, obtain a newer
preview binary from your integration contact and repeat the installation steps.

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
uv pip install --python .venv/bin/python /path/to/akool_modelhub_sdk-0.1.0-py3-none-any.whl -e . --group dev
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
