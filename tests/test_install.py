"""Run the real installer against a local release site and disposable home directories."""

import hashlib
import os
import platform
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "src/akool_modelhub_cli/install.sh"


@pytest.fixture
def release_site(tmp_path):
    site = tmp_path / "site"
    release = site / "releases/0.1.0"
    release.mkdir(parents=True)
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64"}[platform.machine()]
    asset = release / f"akool-mh-{platform.system().lower()}-{arch}"
    payload = b'#!/bin/sh\nprintf "AKOOL Model Hub CLI 0.1.0\\n"\n'
    asset.write_bytes(payload)
    sums = release / "SHA256SUMS"
    sums.write_text(f"{hashlib.sha256(payload).hexdigest()}  {asset.name}\n")
    (site / "latest.txt").write_text("0.1.0\n")

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    home = tmp_path / "home with spaces"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
    for key in ("AKOOL_MH_INSTALL_DIR", "AKOOL_MH_VERSION"):
        env.pop(key, None)
    env["AKOOL_MH_DOWNLOAD_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
    target = home / ".local/bin/akool-mh"

    def run(*args):
        return subprocess.run(
            ["bash", "-s", "--", *args],
            input=SCRIPT.read_text(),
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    try:
        yield run, target, site, asset, sums, env
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_pipe_install_exact_version_and_repeat_preserve_config(release_site):
    run, target, _, _, _, env = release_site
    config = Path(env["HOME"]) / ".akool/modelhub/config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"api_key":"keep-me"}')
    for args in [(), ("--version", "0.1.0")]:
        result = run(*args)
        assert result.returncode == 0, result.stderr
        assert subprocess.check_output([target, "--version"], text=True).strip().endswith("0.1.0")
        assert config.read_text() == '{"api_key":"keep-me"}'
        assert not list(target.parent.glob(".akool-mh-install.*"))


@pytest.mark.parametrize(
    "failure", ["checksum", "missing", "duplicate", "version", "binary", "traversal"]
)
def test_failed_release_preserves_installed_binary(release_site, failure):
    run, target, site, asset, sums, _ = release_site
    target.parent.mkdir(parents=True)
    target.write_text("existing working installation")
    if failure == "checksum":
        asset.write_text("corrupt")
    elif failure == "missing":
        asset.unlink()
    elif failure == "duplicate":
        sums.write_text(sums.read_text() * 2)
    elif failure in ("version", "binary"):
        asset.write_text(
            '#!/bin/sh\necho "wrong version"\n' if failure == "version" else "#!/bin/sh\nexit 1\n"
        )
        sums.write_text(f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}\n")
    else:
        (site / "latest.txt").write_text("../../escape\n")
    result = run()
    assert result.returncode != 0
    assert target.read_text() == "existing working installation"
    assert not list(target.parent.glob(".akool-mh-install.*"))


def test_symlink_target_and_untrusted_http_are_rejected(release_site):
    run, target, _, _, _, _ = release_site
    target.parent.mkdir(parents=True)
    other = target.parent / "other"
    other.write_text("preserve")
    target.symlink_to(other)
    assert run().returncode != 0
    assert other.read_text() == "preserve"
    assert run("--base-url", "http://example.com/cli").returncode != 0


def test_upgrade_uses_same_installer_without_credentials(release_site, monkeypatch):
    from akool_modelhub_cli import main as cli
    from akool_modelhub_cli import upgrade

    _, target, _, _, _, env = release_site
    target.parent.mkdir(parents=True)
    target.write_text("old version")
    monkeypatch.setattr(upgrade.sys, "frozen", True, raising=False)
    monkeypatch.setattr(upgrade.sys, "executable", str(target))
    monkeypatch.setenv("AKOOL_MH_DOWNLOAD_BASE_URL", env["AKOOL_MH_DOWNLOAD_BASE_URL"])
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.delenv("AKOOL_MODELHUB_API_KEY", raising=False)
    assert cli.main(["upgrade", "--target-version", "0.1.0", "--json"]) == 0
    assert subprocess.check_output([target, "--version"], text=True).strip().endswith("0.1.0")


def test_python_installation_does_not_replace_interpreter(monkeypatch):
    from akool_modelhub_cli import upgrade

    monkeypatch.setattr(upgrade.sys, "frozen", False, raising=False)
    with pytest.raises(ValueError, match="pip install"):
        upgrade.upgrade_binary()
