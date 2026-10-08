# CLI release process

Source repository: `https://github.com/AKOOL-Official/model-hub-cli`. Production download
hosting is not yet configured; no public install URL is currently verified as available.

1. Obtain the exact Python SDK wheel required by `pyproject.toml`.
2. Bump the CLI version in `pyproject.toml` and `src/akool_modelhub_cli/main.py`.
3. Run `bash scripts/ci.sh` on native macOS arm64, macOS amd64, Linux arm64 and Linux amd64.
   Set `MODELHUB_SDK_WHEEL=/artifact/path/sdk.whl` before SDK registry publication.
   Linux binaries target glibc systems: build on the oldest supported distribution and
   test/document that baseline. macOS artifacts need signing/notarization for broad public
   release; locally built binaries are ad-hoc signed development artifacts.
4. Run `.venv/bin/python scripts/build_binaries.py` on each target. It runs a packaged
   smoke test and emits `dist/release/VERSION/akool-mh-PLATFORM` and `.sha256`.
5. Collect the four runner outputs, then assemble the static site:

   ```bash
   .venv/bin/python scripts/assemble_release.py /path/to/artifacts --output dist/site
   ```

   All four platforms are required by default. `--platforms darwin-arm64` prepares a
   limited preview for local testing; do not advertise it as a four-platform release.
   Run `.venv/bin/python scripts/smoke_install.py dist/site` to verify pipe installation,
   native self-upgrade, preservation on failure and unchanged credentials against a local server.
6. Upload immutable `dist/site/releases/VERSION/` first and verify those URLs. Then upload
   `install.sh` and update `latest.txt` last. Do not cache latest.txt or the installer for
   long periods. Never overwrite an existing versioned release.
7. Test the hosted installer in a temporary `--install-dir`, verify `--version` and
   `upgrade`. Only then configure the portal's
   `VITE_MODEL_HUB_CLI_INSTALL_URL=https://maas.akool.com/cli/install.sh`.

The installer and upgrader share this download contract:

```text
/cli/install.sh
/cli/latest.txt                         # plain version, e.g. 0.1.0
/cli/releases/0.1.0/SHA256SUMS
/cli/releases/0.1.0/akool-mh-darwin-arm64
/cli/releases/0.1.0/akool-mh-darwin-amd64
/cli/releases/0.1.0/akool-mh-linux-arm64
/cli/releases/0.1.0/akool-mh-linux-amd64
```

Serve `/cli/` as static files separately from API and MCP routing. Downloads need no API
key or repository access. Roll back by pointing `latest.txt` to a prior verified version;
customers may also pin a specific version. No server deployment is needed for the CLI.
