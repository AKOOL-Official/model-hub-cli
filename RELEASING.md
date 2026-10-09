# CLI releases on GitHub

The installer and binaries are hosted entirely on GitHub. No CDN, custom domain or
separate download server is needed.

Customer installation command:

```bash
curl -fsSL https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh | bash
```

`install.sh` at the repository root is the only installer source. Wheel builds include
the same file as `akool_modelhub_cli/install.sh`, used by `akool-mh upgrade` and bundled
into native binaries. Do not maintain a second script in the Python source directory.

## Publish a version

1. Update the version in `pyproject.toml` and `src/akool_modelhub_cli/main.py` together.
2. Review `.github/RELEASE_NOTES.md` and update it for that version.
3. Verify the SDK dependency and pinned SDK revision in `.github/workflows/release.yml`.
   Until the SDK is published to a registry, CI builds a wheel from that immutable Git
   revision, tests it and passes the wheel to each native build. No SDK source is copied
   into this repository or required on the customer's computer.
4. Commit and push the reviewed code to `main`, then create and push its version tag:

   ```bash
   git tag v0.2.1
   git push origin v0.2.1
   ```

   Use a new version for subsequent releases. Never move a tag or overwrite an existing
   release. The workflow checks that the tag matches the package version.
5. Follow **Build and release CLI** in GitHub Actions. It tests and builds macOS arm64,
   macOS amd64, Linux amd64 and Linux arm64. Every runner tests the packaged binary's
   business commands, dynamic model inputs and the GitHub-layout install/upgrade path using a local fake API.
6. Only after all four builds pass, the publish job verifies their hashes, uploads assets
   into a draft, then publishes it as the latest release. It uses the job's `GITHUB_TOKEN`
   with `contents: write`; no personal token or external hosting secret is needed.
7. Verify the public installation command using a temporary `AKOOL_MH_INSTALL_DIR` and
   `akool-mh --version`. Test upgrades without using customer keys or generating media.

Pull requests and manual workflow runs build/test but do not publish. A failed build
cannot publish a partial release. If uploading fails, inspect the draft before removing
or completing it; the workflow refuses to overwrite any existing release.

## Download contract

Each tag `vVERSION` contains:

```text
install.sh
version.txt                            # plain VERSION, without the v prefix
SHA256SUMS
LICENSE
akool-mh-darwin-arm64
akool-mh-darwin-amd64
akool-mh-linux-arm64
akool-mh-linux-amd64
```

The default release base is `https://github.com/AKOOL-Official/model-hub-cli/releases`.
The installer resolves `latest/download/version.txt` once, then downloads the checksum
and binary from `download/vVERSION/`. This prevents an update to “latest” from mixing
versions midway through an installation. Explicit `--version VERSION` skips latest lookup.

Only a published release marked as latest is selected automatically; GitHub prereleases
can be installed by explicit version. The latest published release is the default download channel; product APIs remain in preview.

## Local verification and mirrors

After installing the exact SDK wheel and CLI build dependencies:

```bash
.venv/bin/python scripts/build_binaries.py
.venv/bin/python scripts/assemble_release.py dist/release --layout github --platforms darwin-arm64 --output dist/github-test
.venv/bin/python scripts/smoke_install.py dist/github-test --layout github
```

Select the platform matching the build machine. Omitting `--platforms` requires all
four verified artifacts. `--layout static` still supports a mirror with `latest.txt`
and `releases/VERSION/`; use `AKOOL_MH_DOWNLOAD_BASE_URL` for its root. GitHub release
URLs are recognized automatically; `AKOOL_MH_DOWNLOAD_LAYOUT=github|static` can override
layout detection. Both variables are also honored by `akool-mh upgrade`.

Native compatibility baselines: macOS 14 arm64, macOS 15 Intel, and Ubuntu 22.04/glibc
2.35 for Linux. macOS binaries are ad-hoc signed, not Apple notarized. There is no Windows
or Alpine/musl build. Run on the supported OS/architecture; do not rename one platform's
binary to masquerade as another.

The portal installation URL can point directly to the raw GitHub script after public
verification: `VITE_MODEL_HUB_CLI_INSTALL_URL=https://raw.githubusercontent.com/AKOOL-Official/model-hub-cli/main/install.sh`.

## Live API acceptance

Native installation tests use a fake API and do not establish production service readiness.
Before claiming an environment is ready, run authenticated read-only login/status,
key-scoped model discovery, schema/help and history checks against its actual base URL.
Confirm `/client/capabilities` and `/client/models` are deployed. Do not fall back to the
public model catalog when the key-scoped endpoints are missing. Keep keys in a secret
environment variable or a temporary login configuration; never include them in logs.
Record incomplete checks and server errors separately from CLI test/build success.
