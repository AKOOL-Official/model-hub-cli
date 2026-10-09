## New in 0.2.0

- Pass model inputs directly as `--duration 5`, `--aspect_ratio 16:9` and other exact Schema field names.
- Read model-specific options, required fields and choices with `akool-mh run MODEL_ID --help` or `price MODEL_ID --help`.
- Convert numbers, booleans, arrays and objects using the current authorized model Schema. Preserve text and numeric-looking strings.
- Repeat array flags to collect values; pass booleans as a bare flag or explicit `true`/`false`.
- Reject misspelled long options and invalid values before submitting a generation task.
- Keep `-p` as the prompt shortcut and `-i KEY=VALUE` for every input, including names reserved by CLI controls.

Input precedence: JSON file → model flags (including `-p`) → `-i`. Model-specific help
requires authentication and reads the Schema without creating a task; generic `run --help`
still works offline. Long option abbreviations are no longer accepted.

Upgrade an existing standalone installation with `akool-mh upgrade`.

Install AKOOL Model Hub CLI with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash
```

The installer detects your OS and architecture, verifies the SHA256 checksum, and installs
`akool-mh` into `~/.local/bin`. No Git, Python, Node.js or sudo is needed.
If this directory is not already on PATH, follow the printed shell configuration instruction.

Then run `akool-mh login` with a Model Hub API Key and `akool-mh status` to verify access.
Use `akool-mh upgrade` for subsequent standalone updates.

Included platforms and build verification:

- macOS arm64: built and tested on macOS 14.
- macOS Intel: built and tested on macOS 15.
- Linux amd64 and arm64: built and tested on Ubuntu 22.04 (glibc 2.35+); Alpine/musl is not supported.

Every binary passes business command, dynamic input, model help and installation/upgrade checks using
a local fake API and disposable credentials. macOS binaries are ad-hoc signed, not Apple
notarized. No real model generation is performed by the release tests.

This is the 0.2.0 release; the CLI API may evolve. The SDK is bundled into the
binary from the pinned revision recorded in `.github/workflows/release.yml`.
