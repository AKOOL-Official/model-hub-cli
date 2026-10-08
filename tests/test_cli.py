import io
import json
from types import SimpleNamespace

import httpx
import pytest
from akool_modelhub_sdk import AsyncModelHub

from akool_modelhub_cli import config
from akool_modelhub_cli import main as cli


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AKOOL_MODELHUB_API_KEY", "sk-cli-secret")
    monkeypatch.setenv("AKOOL_MODELHUB_BASE_URL", "https://example.invalid/gateway/api/v1")
    monkeypatch.delenv("MODEL_HUB_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_HUB_BASE_URL", raising=False)
    path = tmp_path / ".akool" / "modelhub" / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.setattr(cli, "config_path", lambda: path)
    return path


@pytest.fixture
def mock_api(monkeypatch, cli_env):
    calls = []
    state = SimpleNamespace(status="completed", broken_submit=False, count=0)

    def handle(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("capabilities"):
            return httpx.Response(
                200,
                json={
                    "contract_version": "test",
                    "run_idempotency_v1": True,
                    "idempotency_header": "X-Request-Id",
                },
            )
        if path.endswith("models/detail"):
            return httpx.Response(
                200,
                json={
                    "model_id": "vendor/model",
                    "parameters": [
                        {"key": "prompt", "type": "text", "required": True},
                        {"key": "size", "type": "number", "min": 1, "max": 10},
                    ],
                    "examples": [],
                    "output_schema": None,
                },
            )
        if path.endswith("/models"):
            return httpx.Response(200, json={"total": 1, "items": [{"model_id": "vendor/model"}]})
        if path.endswith("/pricing/preview"):
            return httpx.Response(
                200, json={"list_price": 1, "final_price": 1, "discount_rate": 1, "you_save": 0}
            )
        if request.method == "POST" and "/run/" in path:
            state.count += 1
            if state.broken_submit:
                raise httpx.ReadTimeout("lost response")
            return httpx.Response(
                200,
                json={
                    "task_uuid": request.headers["X-Request-Id"],
                    "status": "pending",
                    "amount": 1,
                },
            )
        task = {
            "task_uuid": path.rsplit("/", 1)[-1],
            "model_id": "vendor/model",
            "status": state.status,
            "output": {"url": "https://example.invalid/result.png"},
            "pool_code": "private",
            "meta_info": {"secret": 1},
        }
        if path.endswith("/run/tasks"):
            return httpx.Response(200, json={"total": 1, "items": [task]})
        if "/run/tasks/" in path:
            return httpx.Response(200, json=task)
        raise AssertionError(path)

    monkeypatch.setattr(
        cli,
        "make_client",
        lambda configuration, args: AsyncModelHub(
            api_key=configuration.api_key,
            base_url=configuration.base_url,
            timeout=args.request_timeout,
            max_retries=0,
            transport=httpx.MockTransport(handle),
        ),
    )
    return calls, state


@pytest.mark.parametrize("argv", [["--json", "status"], ["status", "--json"]])
def test_global_json_anywhere_and_status_redaction(argv, mock_api, capsys):
    assert cli.main(argv) == 0
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert data["authenticated"] is True
    assert "sk-cli-secret" not in output.out + output.err
    assert all(request.method == "GET" for request in mock_api[0])


def test_run_returns_task_id_without_wait_and_preserves_input(mock_api, capsys, tmp_path):
    payload = tmp_path / "input.json"
    payload.write_text(json.dumps({"prompt": "from file", "size": 2, "keep": [False, None]}))
    argv = [
        "--json",
        "run",
        "vendor/model",
        "--input-file",
        str(payload),
        "-p",
        "literal prompt",
        "-i",
        "size=4",
        "--request-id",
        "original-id",
    ]
    assert cli.main(argv) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["task_uuid"] == "original-id"
    assert json.loads(output.out)["status"] == "pending"
    assert "Task ID: original-id" in output.err
    posted = next(request for request in mock_api[0] if request.method == "POST")
    assert posted.url.path == "/gateway/api/v1/run/vendor/model"
    assert json.loads(posted.content)["input"] == {
        "prompt": "literal prompt",
        "size": 4,
        "keep": [False, None],
    }
    assert not any("/run/tasks/" in request.url.path for request in mock_api[0])


def test_run_wait_and_result_recovery_do_not_duplicate_create(mock_api, capsys):
    assert (
        cli.main(
            ["run", "vendor/model", "-p", "scene", "--request-id", "original", "--wait", "--json"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert cli.main(["result", "original", "--wait", "--json"]) == 0
    output = capsys.readouterr().out
    assert "private" not in output and "secret" not in output
    assert mock_api[1].count == 1


def test_run_timeout_and_failure_exit_codes(mock_api, capsys):
    mock_api[1].status = "processing"
    assert cli.main(["result", "original", "--wait", "--timeout", "0.01", "--json"]) == 4
    assert json.loads(capsys.readouterr().out)["task_uuid"] == "original"
    mock_api[1].status = "failed"
    assert cli.main(["result", "original", "--wait", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_unknown_submission_keeps_id_and_exit_code(mock_api, capsys):
    mock_api[1].broken_submit = True
    assert (
        cli.main(["run", "vendor/model", "-p", "scene", "--request-id", "original", "--json"]) == 5
    )
    assert json.loads(capsys.readouterr().out)["task_uuid"] == "original"
    assert mock_api[1].count == 1


@pytest.mark.parametrize(
    "args",
    [
        ["run", "vendor/model"],
        ["run", "vendor/model", "-p", "scene", "-i", "size=99"],
        ["run", "../bad", "-p", "scene"],
        ["run", "vendor/model", "-p", "scene", "-i", "=empty"],
        ["run", "vendor/model", "-p", "scene", "--timeout", "nan"],
        ["run", "vendor/model", "-p", "scene", "-i", "size=NaN"],
    ],
)
def test_bad_input_never_submits(args, mock_api, capsys):
    assert cli.main([*args, "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]
    assert not any(request.method == "POST" for request in mock_api[0])


def test_input_file_stdin_and_override(monkeypatch):
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO('{"prompt":"original","nested":{"a":true}}'))
    args = cli.build_parser().parse_args(
        ["run", "m", "--input-file", "-", "-p", "unchanged text", "-i", "items=[1,false]"]
    )
    assert cli.read_input(args) == {
        "prompt": "unchanged text",
        "nested": {"a": True},
        "items": [1, False],
    }


def test_help_and_version_work_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("AKOOL_MODELHUB_API_KEY", raising=False)
    monkeypatch.setattr(cli, "make_client", lambda *_: pytest.fail("network client created"))
    for argv in [["--help"], ["run", "vendor/model", "--help"], ["--version"]]:
        with pytest.raises(SystemExit) as caught:
            cli.main(argv)
        assert caught.value.code == 0
    assert "akool-mh" in capsys.readouterr().out


def test_unknown_option_is_machine_readable(capsys):
    assert cli.main(["--json", "not-a-command"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_arguments"


def test_login_verifies_before_writing_and_logout_preserves_base(
    mock_api, cli_env, monkeypatch, capsys
):
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *args, **kwargs: "sk-new-secret")
    assert cli.main(["login", "--json"]) == 0
    out = capsys.readouterr().out
    assert "sk-new-secret" not in out
    assert json.loads(cli_env.read_text())["api_key"] == "sk-new-secret"
    assert cli_env.stat().st_mode & 0o777 == 0o600
    assert cli_env.parent.stat().st_mode & 0o777 == 0o700
    assert cli.main(["logout", "--json"]) == 0
    assert "api_key" not in json.loads(cli_env.read_text())
    assert "base_url" in json.loads(cli_env.read_text())
    assert json.loads(capsys.readouterr().out)["environment_key_present"]


def test_failed_login_does_not_overwrite_credentials(cli_env, monkeypatch, capsys):
    config.write_config({"api_key": "sk-preserve", "base_url": "https://example.invalid/api/v1"})
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *args, **kwargs: "sk-rejected")
    monkeypatch.setattr(
        cli,
        "make_client",
        lambda cfg, args: AsyncModelHub(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(401, json={"error": {"message": "Invalid sk-rejected"}})
            ),
        ),
    )
    assert cli.main(["login", "--json"]) == 1
    assert "sk-rejected" not in capsys.readouterr().out
    assert config.read_config()["api_key"] == "sk-preserve"
