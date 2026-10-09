<div align="center">

# AKOOL Model Hub CLI

**Discover models. Preview pricing. Run AI tasks from your terminal.**

[![Version: 0.2.1 preview](https://img.shields.io/badge/version-0.2.1_preview-2563eb)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

[Install](#install) · [Walkthrough](#walkthrough) · [Inputs](#command-line-inputs) · [Commands](#command-reference) · [Troubleshooting](#troubleshooting)

</div>

`akool-mh` lets you search models, inspect their inputs, estimate prices and run generation
from your terminal. The standalone binary needs no Git, Python or Node.js.

## Install

Run this command on **macOS or Linux**:

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash
```

**Example output** — your installation path will differ:

```text
Installed akool-mh 0.2.1 at /Users/alex/.local/bin/akool-mh
```

The installer selects your platform, verifies its SHA256 checksum and installs to
`~/.local/bin` without `sudo`. Check your installed version:

```bash
akool-mh --version
```

**Output:**

```text
AKOOL Model Hub CLI 0.2.1
```

If the command is not found, follow the installer's PATH instructions. For the current
terminal, run `export PATH="$HOME/.local/bin:$PATH"`; add the same line to `~/.zshrc`
or `~/.bashrc` to keep it for new terminals.

<details>
<summary><strong>Platforms and installation alternatives</strong></summary>

Current release: [v0.2.1](https://github.com/AKOOL-Official/model-hub-cli/releases/tag/v0.2.1).

| Platform | Build and test environment |
| --- | --- |
| macOS · Apple Silicon (arm64) | macOS 14 |
| macOS · Intel (amd64) | macOS 15 |
| Linux · amd64 / arm64 | Ubuntu 22.04, glibc 2.35+ |

Windows and Alpine/musl binaries are not currently provided. macOS binaries are ad-hoc
signed, not Apple notarized.

To pin a version:

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash -s -- --version 0.2.1
```

This prints the same installation message shown above. Add `--install-dir ~/.local/bin`
after `bash -s --` to choose a directory. The script needs Bash, curl and either
`shasum` or `sha256sum`; you can inspect [install.sh](install.sh) before running it.

**Python 3.11+ alternative:** obtain the CLI wheel and the matching
`akool-modelhub-sdk==0.1.0` wheel from your integration contact. With both files in the
same directory, run:

```bash
python -m pip install --find-links . ./akool_modelhub_cli-0.2.1-py3-none-any.whl
```

Pip reports the installed packages. Neither Python package is published to a public
registry yet; use the standalone installer for the simplest setup.

</details>

## Walkthrough

> [!NOTE]
> The examples below use the **fictional model `example/video-generator`**, a sample task
> ID, illustrative prices and an example result URL. Replace the model ID with one returned
> by your own `models` command and the task ID with your own task's ID. They are written
> directly in each command, so no Shell variables are needed.
>
> Outputs labeled **excerpt** show selected fields. Your actual response may contain more
> fields; model inputs, prices and output URLs depend on your model and account.

### 1. Log in

Create a **Model Hub API Key** in your account, then run:

```bash
akool-mh login
```

**Example interaction** — key entry is hidden:

```text
Model Hub API key:
{
  "authenticated": true,
  "base_url": "https://maas.akool.com/api/v1",
  "config_path": "/Users/alex/.akool/modelhub/config.json",
  "environment_override": false
}
```

`login` validates the key before saving it. Only the API key is required. The default
base URL is `https://maas.akool.com`; the CLI appends `/api/v1` automatically and reports
the resolved API root in its output. Main-site AKOOL Client ID / Client Secret credentials
are separate.

<details>
<summary><strong>Check your connection or use another API root</strong></summary>

```bash
akool-mh status
```

**Example output (excerpt):**

```json
{
  "authenticated": true,
  "base_url": "https://maas.akool.com/api/v1",
  "credential_source": "local_config"
}
```

`status` does not create a generation task. For FAT, use:

```bash
akool-mh login --base-url https://maas-fat.akool.io
akool-mh status
```

Enter the FAT API key at the hidden prompt. The CLI resolves the address to
`https://maas-fat.akool.io/api/v1`. In v0.2.1+, domain-only URLs, gateway prefixes such
as `https://landing-fat.akool.io/interface/maas-backend`, and complete API roots ending
in `/api/v1` all work; the suffix is never added twice. The base URL is saved after a
successful login, so it need not be repeated on subsequent commands.

**Service readiness:** a valid key and a working login do not guarantee that every
backend capability is deployed. The service must expose `/api/v1/client/capabilities`
and `/api/v1/client/models` for the model workflow. If these return 404, the operator
needs to deploy the matching backend or fix routing. A non-JSON response usually means
the request reached a web page rather than the API; changing or repasting the key will
not fix that routing problem.

</details>

### 2. Find a model

```bash
akool-mh models video --limit 1
```

**Example output (excerpt):**

```json
{
  "items": [
    {
      "model_id": "example/video-generator",
      "name": "Example Video Generator",
      "task_type": "video"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 1
}
```

Use the returned `model_id` in subsequent commands. Results include only models your API
key can access. Search with another keyword, such as `image`, or omit the keyword to browse.

### 3. Inspect its parameters

```bash
akool-mh run example/video-generator --help
```

**Example output (model input excerpt):**

```text
Model inputs for "example/video-generator":
  --prompt, -p  [string] (required)
    description: "Describe the video to generate."
  --duration  [enum]
    enum: [5, 10]
    default: 5
  --aspect_ratio  [enum]
    enum: ["16:9", "9:16"]
    default: "16:9"
```

This example model accepts `--prompt`, `--duration` and `--aspect_ratio`. Your model's
options may differ. Model-specific help needs an API key and reads the Schema without
creating a task. `akool-mh run --help` shows generic help offline.

<details>
<summary><strong>View the input and output Schema</strong></summary>

```bash
akool-mh schema example/video-generator
```

**Example output (excerpt):**

```json
{
  "model_id": "example/video-generator",
  "input_schema": {
    "type": "object",
    "properties": {
      "prompt": {
        "type": "string",
        "description": "Describe the video to generate."
      },
      "duration": {
        "enum": [
          5,
          10
        ],
        "default": 5
      },
      "aspect_ratio": {
        "enum": [
          "16:9",
          "9:16"
        ],
        "default": "16:9"
      }
    },
    "required": [
      "prompt"
    ]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "video_url": {
        "type": "string",
        "format": "uri"
      }
    }
  }
}
```

The full response also includes other advertised input fields, the Schema hash, warnings
and any model examples. `output_schema` describes what to expect in a completed task's output.

</details>

### 4. Preview the price

```bash
akool-mh price example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duration 5 \
  --aspect_ratio 16:9
```

**Example output (excerpt; amounts are illustrative):**

```json
{
  "list_price": 0.05,
  "discount_rate": 1.0,
  "final_price": 0.05,
  "you_save": 0.0,
  "binding": false
}
```

This does not generate media. `binding: false` means the result is an estimate, not a
binding charge. Use the same inputs when you submit the task.

### 5. Generate and wait

The following command submits **one billable generation task**:

```bash
akool-mh run example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duration 5 \
  --aspect_ratio 16:9 \
  --wait
```

The CLI prints a task ID to **stderr** before submission:

```text
Task ID: 8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123
```

When the task completes, **stdout** contains the result. **Example output (excerpt):**

```json
{
  "task_uuid": "8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123",
  "model_id": "example/video-generator",
  "status": "completed",
  "output": {
    "video_url": "https://example.com/results/lake.mp4"
  },
  "amount": 0.05,
  "error": null
}
```

`status: completed` means the task finished. Read the model-specific fields in `output`;
this example returns a video URL. There is no universal `outputs[0]` field, and the CLI
does not automatically download the media.

<details>
<summary><strong>Submit without waiting</strong></summary>

As an alternative to the command above, omit `--wait`:

```bash
akool-mh run example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duration 5 \
  --aspect_ratio 16:9
```

**Example output (excerpt):**

```json
{
  "task_uuid": "8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123",
  "status": "pending",
  "estimated_time": 20,
  "output": null
}
```

Keep the returned task ID and check it with `result`. Each new `run` normally creates a
new generation; use `result` to check an existing task instead of submitting again.

</details>

### 6. Check or resume the task

Use the `task_uuid` returned by your own submission:

```bash
akool-mh result 8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123 --wait --timeout 600
```

**Example output after completion (excerpt):**

```json
{
  "task_uuid": "8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123",
  "model_id": "example/video-generator",
  "status": "completed",
  "output": {
    "video_url": "https://example.com/results/lake.mp4"
  },
  "amount": 0.05,
  "error": null
}
```

Omit `--wait` to check once. A timeout or Ctrl-C stops local waiting and **does not cancel
the backend task**. You can run `result` again with the same ID.

<details>
<summary><strong>View task history</strong></summary>

```bash
akool-mh history --limit 1
```

**Example output (excerpt):**

```json
{
  "items": [
    {
      "task_uuid": "8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123",
      "model_id": "example/video-generator",
      "status": "completed",
      "output": {
        "video_url": "https://example.com/results/lake.mp4"
      }
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 1,
  "visibility": "account"
}
```

History belongs to the account and includes tasks across its keys. Use the listed task IDs
with `result`; add `--model example/video-generator` to filter this model's history.

</details>

## Command-line inputs

Use the model's **exact field name** as `--FIELD VALUE`, after the model ID. The CLI reads
its current Schema, converts types and validates the inputs before submission. Underscores
and hyphens are distinct: `aspect_ratio` becomes `--aspect_ratio`.

| Schema type | Example argument | Behavior |
| --- | --- | --- |
| String | `--prompt "A red ceramic cup"` | Preserves the text |
| Number / integer | `--duration 5` | Converts to a number and checks constraints |
| Boolean | `--enhance` or `--enhance false` | Bare flag means `true` |
| Enum | `--aspect_ratio 16:9` | Accepts only advertised choices |
| Array | `--image_urls https://example.com/a.png --image_urls https://example.com/b.png` | Collects values in order; a JSON array also works |
| Object | `--settings '{"seed":123}'` | Parses a JSON object |
| Numeric-looking string | `--voice_id 00123` | Preserves `00123` when the Schema expects a string |

These are syntax examples; a field must exist in the selected model's Schema. Quote spaces
and shell characters. For text beginning with a dash, use `--prompt="--keep this text"`.
Omitted inputs are not filled with client-side defaults.

<details>
<summary><strong>Use -p or -i, including reserved field names</strong></summary>

`-p` is a shortcut for `--prompt`. `-i KEY=VALUE` works for every model input. These three
commands pass the same prompt and return the same kind of price response:

```bash
akool-mh price example/video-generator --prompt "A red ceramic cup"
akool-mh price example/video-generator -p "A red ceramic cup"
akool-mh price example/video-generator -i 'prompt=A red ceramic cup'
```

**Example output for each command (excerpt):**

```json
{
  "final_price": 0.05,
  "binding": false
}
```

CLI controls such as `--wait`, `--json` and `--timeout` keep their own meanings. For a model
field also called `timeout`, use `-i timeout=30`; `--timeout 600` still controls how long
the CLI waits. Model-specific help marks these collisions.

`-i` parses valid JSON and otherwise uses a string. To force a numeric-looking string,
write `-i 'voice_id="00123"'`. It can also pass unusual field names or additional inputs
allowed by the Schema. Dynamic long flags only accept advertised fields.

</details>

<details>
<summary><strong>Optional JSON files and input precedence</strong></summary>

Files are useful for long arrays, nested objects or saved inputs, but are not required.
For example, save this as `input.json`:

```json
{
  "prompt": "A slow camera pan across a mountain lake",
  "duration": 5,
  "aspect_ratio": "16:9"
}
```

```bash
akool-mh price example/video-generator --input-file input.json
```

This produces the same price response shown in step 4. `--input-file -` reads from stdin.
You can override file fields with command-line options.

Precedence: **JSON file → model flags (including `-p`) → `-i KEY=VALUE`**, regardless of
argument order. Repeated scalar flags use the last value; repeated array flags collect values.

</details>

## Scripts and JSON output

Supply `AKOOL_MODELHUB_API_KEY` through your CI secret store or environment; interactive
`login` is unnecessary. Optionally set `AKOOL_MODELHUB_BASE_URL` for another API root.

Add `--json` to get one compact JSON value on stdout:

```bash
akool-mh price example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duration 5 \
  --aspect_ratio 16:9 \
  --json
```

**Example output:**

```json
{"request_id": "example-response-id", "list_price": 0.05, "discount_rate": 1.0, "final_price": 0.05, "discount_reason": null, "you_save": 0.0, "pricing_window": null, "binding": false}
```

`--json` controls **output formatting**, not input format. Diagnostics and task-ID notices
remain on stderr. Check the exit code and the task's `status`: a successful submission can
still be pending.

<details>
<summary><strong>Explicit request IDs and recovery</strong></summary>

For automation, create and save a unique request ID before submission. Supply it directly:

```bash
akool-mh run example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duration 5 \
  --aspect_ratio 16:9 \
  --request-id 8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123
```

**Example output (excerpt):**

```json
{
  "task_uuid": "8f6c2d7a-3b91-4e65-9a02-6c7d8e9f0123",
  "status": "pending",
  "estimated_time": 20,
  "output": null
}
```

Use your own saved UUID or unique ID of at most 36 characters, not this example's ID.
If a submission's outcome is unknown, query that original ID with `result` first. If replay
is needed, keep the **same ID, model and exact input**. A new ID creates a new generation
and may incur another charge. Automatic submit retries require backend idempotency.

</details>

## Troubleshooting

### Missing required inputs

Pass the model's required fields when estimating a price or submitting a task. For example:

```bash
akool-mh price bytedance/seedance-v1.5-pro/image-to-video-spicy
```

**Example output in v0.2.1** — based on this model's FAT Schema, which requires `first_frame`:

```json
{
  "request_id": null,
  "task_uuid": null,
  "error": {
    "code": "invalid_arguments",
    "message": "Missing required fields: first_frame. Provide --first_frame VALUE; see akool-mh price bytedance/seedance-v1.5-pro/image-to-video-spicy --help.",
    "status_code": null,
    "missing_fields": ["first_frame"],
    "field_options": {"first_frame": "--first_frame VALUE"}
  }
}
```

Supply a server-accessible image URL as `--first_frame`, using a real input for your task.
If several fields are missing, the CLI lists all of them. Nested fields include their
paths, such as `settings.steps` or `items[0].url`; the suggested option updates the parent
object/array rather than inventing unsupported dotted flags. CLI-reserved names use `-i`.
Exit code `2` indicates local validation failure; no price or generation request is sent.

### A misspelled model parameter

```bash
akool-mh price example/video-generator \
  --prompt "A slow camera pan across a mountain lake" \
  --duraton 5
```

**Example output** — exit code `2`, no generation submitted:

```json
{
  "request_id": null,
  "task_uuid": null,
  "error": {
    "code": "invalid_arguments",
    "message": "Unknown model input --duraton. Did you mean --duration? Use run MODEL_ID --help.",
    "status_code": null
  }
}
```

Correct the option to `--duration`. To check valid fields and choices, use
`akool-mh run example/video-generator --help`.

| Problem | What to do |
| --- | --- |
| `akool-mh: command not found` | Add `~/.local/bin` to PATH; see [Install](#install) |
| Installer returns a web page | Use the raw GitHub URL above, not a `/blob/` page |
| `Non-JSON Model Hub response` | Check the resolved API root and gateway routing; HTML is not a key-validation result |
| `401` / authentication failed | Check the Model Hub API Key, its expiry and the API root |
| `403` / access denied | Check key permissions and IP restrictions |
| Model missing / `404` | Search with the same key and use the exact returned model ID |
| Invalid input / `400` / `422` | Check required fields, types and choices in model help or Schema |
| `429` / rate limited | Respect the response's retry interval |
| Waiting timed out | Query the same task with `result`; do not create another task |

<details>
<summary><strong>Exit codes, global options and credentials</strong></summary>

| Exit code | Meaning |
| --- | --- |
| `0` | Command succeeded; a submitted task may still be pending |
| `1` | Service, authentication or network error |
| `2` | Invalid arguments, input or configuration |
| `3` | Task failed or was cancelled |
| `4` | Waiting deadline expired |
| `5` | Submission outcome unknown; recover the original ID |
| `130` | Interrupted locally |

| Option | Behavior |
| --- | --- |
| `--json` | Compact JSON output; works before or after the command |
| `--base-url URL` | Override the service URL or gateway prefix; `/api/v1` is appended when absent |
| `--request-timeout SECONDS` | Limit each HTTP operation; default: 90 seconds |
| `--timeout SECONDS` | Limit waiting with `run --wait` or `result --wait`; default: 600 seconds |

Base URL priority: explicit flag → `AKOOL_MODELHUB_BASE_URL` → saved configuration →
`https://maas.akool.com`. The CLI resolves the API root by appending `/api/v1` once. The environment API key overrides the locally saved key.
Local login uses `~/.akool/modelhub/config.json`, separate from the main AKOOL CLI's
`~/.akool/config.json`. Keep credentials out of prompts, input JSON and issue reports.

Media inputs must be server-accessible HTTPS URLs. Local paths and `@file` do not upload files.

</details>

## Updates and logout

Update the standalone CLI:

```bash
akool-mh upgrade
```

**Example output** — paths and version depend on your installation:

```json
{
  "updated": true,
  "path": "/Users/alex/.local/bin/akool-mh",
  "message": "Installed akool-mh 0.2.1 at /Users/alex/.local/bin/akool-mh"
}
```

Upgrades preserve credentials. Use `akool-mh upgrade --target-version 0.2.1` to select a
published version. Python package installations update with pip instead of `upgrade`.

To remove the locally saved API key:

```bash
akool-mh logout
```

**Example output:**

```json
{
  "local_credentials_removed": true,
  "environment_key_present": false
}
```

If `environment_key_present` is `true`, an environment key is still active; unset it
separately. `logout` keeps your saved API root.

## Command reference

| Command | Purpose |
| --- | --- |
| `login` / `status` / `logout` | Set up, verify or remove local credentials |
| `models` | Discover models available to your key |
| `schema` | Inspect a model's input/output Schema and examples |
| `price` | Estimate a generation's price without submitting it |
| `run` | Submit a task; add `--wait` for its result |
| `result` | Query or wait for an existing task |
| `history` | List account-level tasks |
| `upgrade` | Update the standalone CLI from GitHub Releases |

Every command accepts `--help`. Dynamic model flags and model-specific help require v0.2.0+.

## Support and development

[Open an issue](https://github.com/AKOOL-Official/model-hub-cli/issues) with your version,
operating system and error message. Remove credentials and private input before posting.
For application integration, use the [Python SDK](https://github.com/AKOOL-Official/model-hub-sdk-python)
or [TypeScript SDK](https://github.com/AKOOL-Official/model-hub-sdk-typescript).

<details>
<summary><strong>Build from source</strong></summary>

Development requires Python 3.11+ and uv. Before SDK registry publication, obtain its
matching wheel artifact. From this repository's root:

```bash
uv venv
uv pip install --python .venv/bin/python /path/to/akool_modelhub_sdk-0.1.0-py3-none-any.whl . --group dev
.venv/bin/python -m pytest
.venv/bin/ruff check src tests scripts
uv build --out-dir dist
.venv/bin/python scripts/build_binaries.py
```

The build bundles the SDK and runtime, then exercises the CLI against a fake local API.
See [CI.md](CI.md) for CI and [RELEASING.md](RELEASING.md) for native releases.

</details>

## License

[MIT](LICENSE) · Copyright (c) 2026 AKOOL.
