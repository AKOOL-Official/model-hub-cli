## New in 0.2.1

- List all missing required input fields by name, with the corresponding CLI options, instead of `violates required`.
- Report nested object and array paths such as `settings.steps` and `items[0].url`; return `error.missing_fields` and `error.field_options` for scripts.
- Keep customer values out of validation errors and stop before price/task submission when required inputs are missing.

- Only the Model Hub API key is required; `base_url` is optional and defaults to `https://maas.akool.com`.
- Accept domain-only URLs such as `https://maas-fat.akool.io`, gateway prefixes and existing `/api/v1` roots. Append `/api/v1` exactly once.
- Explain non-JSON responses as API-root/routing errors rather than leaving users to suspect their key.
- Keep previously saved full API roots compatible and preserve credentials after a failed login.

Test FAT with `akool-mh login --base-url https://maas-fat.akool.io` and enter the FAT key
at the hidden prompt. The service must have the matching client endpoints deployed;
this CLI release does not deploy backend routes or repair server-side HTTP 500 errors.

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

This is the 0.2.1 release; the CLI API may evolve. The SDK is bundled into the
binary from the pinned revision recorded in `.github/workflows/release.yml`.
