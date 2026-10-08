"""Exercise a real packaged CLI's pipe installation, upgrade and failure rollback locally."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path, help="Output directory from assemble_release.py")
    args = parser.parse_args()
    site = args.site.resolve()
    version = (site / "latest.txt").read_text().strip()

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="akool-mh-install-") as directory:
            home = Path(directory)
            install_dir = home / "bin with spaces"
            config = home / ".akool/modelhub/config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"api_key":"sk-local-smoke-only"}\n')
            base = f"http://127.0.0.1:{server.server_port}"
            env = {
                **os.environ,
                "HOME": str(home),
                "NO_PROXY": "127.0.0.1",
                "no_proxy": "127.0.0.1",
                "AKOOL_MH_DOWNLOAD_BASE_URL": base,
                "AKOOL_MH_INSTALL_DIR": str(install_dir),
            }
            for name in ("AKOOL_MODELHUB_API_KEY", "AKOOL_MODELHUB_BASE_URL", "AKOOL_MH_VERSION"):
                env.pop(name, None)
            # Equivalent to curl ... | bash, with no shell interpolation of file paths.
            with subprocess.Popen(
                ["curl", "-fsSL", base + "/install.sh"], stdout=subprocess.PIPE, env=env
            ) as curl:
                result = subprocess.run(
                    ["bash"],
                    stdin=curl.stdout,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                curl.stdout.close()
                assert curl.wait(timeout=10) == 0
            assert result.returncode == 0, result.stderr
            binary = install_dir / "akool-mh"
            assert (
                subprocess.check_output([binary, "--version"], text=True).strip()
                == f"AKOOL Model Hub CLI {version}"
            )
            result = subprocess.run(
                [binary, "upgrade", "--target-version", version, "--json"],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, (result.stdout, result.stderr)
            assert json.loads(result.stdout)["updated"] is True
            assert config.read_text() == '{"api_key":"sk-local-smoke-only"}\n'
            before = hashlib.sha256(binary.read_bytes()).hexdigest()
            result = subprocess.run(
                [binary, "upgrade", "--target-version", "999.0.0", "--json"],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 1
            assert json.loads(result.stdout)["error"]
            assert hashlib.sha256(binary.read_bytes()).hexdigest() == before
            assert config.read_text() == '{"api_key":"sk-local-smoke-only"}\n'
            print(
                "Native binary: pipe install, upgrade, failure preservation and credentials passed"
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
