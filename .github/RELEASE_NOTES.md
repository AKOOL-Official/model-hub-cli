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

Every binary passes seven CLI command checks and installation/upgrade smoke tests using
a local fake API and disposable credentials. macOS binaries are ad-hoc signed, not Apple
notarized. No real model generation is performed by the release tests.

This is the initial 0.1.0 release; the CLI API may evolve. The SDK is bundled into the
binary from the pinned revision recorded in `.github/workflows/release.yml`.
