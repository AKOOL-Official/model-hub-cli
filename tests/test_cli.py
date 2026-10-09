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
    state = SimpleNamespace(
        status="completed",
        broken_submit=False,
        count=0,
        schema_status=200,
        parameters=[
            {"key": "prompt", "type": "text", "required": True},
            {"key": "size", "type": "number", "min": 1, "max": 10},
            {"key": "duration", "type": "select", "options": [{"value": 5}, {"value": 10}]},
            {
                "key": "aspect_ratio",
                "type": "select",
                "options": [{"value": "16:9"}, {"value": "1:1"}],
            },
            {"key": "enabled", "type": "boolean"},
            {"key": "identifier", "type": "text"},
            {"key": "offset", "type": "number"},
            {"key": "references", "type": "image_upload_group", "min_count": 2, "max_count": 3},
            {
                "key": "settings",
                "type": "object",
                "object_properties": [
                    {"key": "steps", "type": "number", "max": 10, "required": True},
                ],
            },
        ],
    )

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
                state.schema_status,
                json={
                    "model_id": "vendor/model",
                    "parameters": state.parameters,
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
    for argv in [["--help"], ["run", "--help"], ["price", "--help"], ["--version"]]:
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


@pytest.mark.parametrize("command", ["run", "price"])
def test_model_long_options_preserve_types_and_cli_controls(command, mock_api, capsys):
    argv = [
        "--json",
        command,
        "vendor/model",
        "--prompt",
        "literal prompt",
        "--duration",
        "5",
        "--aspect_ratio=16:9",
        "--enabled",
        "--identifier",
        "00123",
        "--offset",
        "-1e-3",
        "--settings",
        '{"steps":3}',
        "--references",
        "https://example.com/a.png",
        "--references",
        "https://example.com/b.png",
    ]
    if command == "run":
        argv.extend(["--request-id", "dynamic-task", "--wait", "--timeout", "5"])
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)
    posts = [r for r in mock_api[0] if r.method == "POST"]
    assert len(posts) == 1
    body = json.loads(posts[0].content)
    assert body["input" if command == "run" else "input_params"] == {
        "prompt": "literal prompt",
        "duration": 5,
        "aspect_ratio": "16:9",
        "enabled": True,
        "identifier": "00123",
        "offset": -0.001,
        "settings": {"steps": 3},
        "references": ["https://example.com/a.png", "https://example.com/b.png"],
    }
    assert sum(r.url.path.endswith("/models/detail") for r in mock_api[0]) == 1


@pytest.mark.parametrize(
    "prompt_args", [["-p", "scene"], ["--prompt=scene"], ["-i", "prompt=scene"], ["-pscene"]]
)
def test_prompt_shortcut_and_input_fallback(prompt_args, mock_api, capsys):
    assert cli.main(["price", "vendor/model", *prompt_args, "--json"]) == 0
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert json.loads(post.content)["input_params"] == {"prompt": "scene"}


@pytest.mark.parametrize(
    "value", ["123", "false", "null", '{"unchanged":true}', "--wait", "-negative"]
)
def test_schema_strings_are_preserved_exactly(value, mock_api, capsys):
    assert cli.main(["price", "vendor/model", f"--prompt={value}", "--json"]) == 0
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert json.loads(post.content)["input_params"]["prompt"] == value


def test_file_flags_and_input_override_precedence(mock_api, capsys, tmp_path):
    payload = tmp_path / "input.json"
    payload.write_text('{"prompt":"file","size":1,"duration":10,"keep":true}')
    assert (
        cli.main(
            [
                "price",
                "vendor/model",
                "--input-file",
                str(payload),
                "--prompt",
                "first",
                "-plast",
                "-i",
                "size=4",
                "--size",
                "99",
                "--duration",
                "6",
                "--duration",
                "5",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert json.loads(post.content)["input_params"] == {
        "prompt": "last",
        "size": 4,
        "duration": 5,
        "keep": True,
    }


def test_reserved_names_and_internal_destinations_cannot_change_cli_behavior(mock_api, capsys):
    mock_api[1].parameters.extend(
        [
            {"key": "timeout", "type": "number"},
            {"key": "json", "type": "boolean"},
            {"key": "model_id", "type": "text"},
            {"key": "input_file", "type": "text"},
        ]
    )
    assert (
        cli.main(
            [
                "run",
                "vendor/model",
                "--prompt",
                "scene",
                "--model_id",
                "different/model",
                "--input_file",
                "not-read.json",
                "--timeout",
                "5",
                "--wait",
                "-i",
                "timeout=9",
                "-i",
                "json=false",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert post.url.path.endswith("/run/vendor/model")
    assert json.loads(post.content)["input"] == {
        "prompt": "scene",
        "model_id": "different/model",
        "input_file": "not-read.json",
        "timeout": 9,
        "json": False,
    }


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--duraton", "5"], "Did you mean --duration"),
        (["--dur", "5"], "Unknown model input"),
        (["--request-ti", "5"], "Unknown model input"),
        (["--duration"], "requires a value"),
        (["--duration", "--wait"], "requires a value"),
        (["--duration", "6"], "enum"),
        (["--size", "zero"], "type"),
        (["--size", "NaN"], "type"),
        (["--size", "99"], "maximum"),
        (["--enabled", "maybe"], "type"),
        (["--references", "https://example.com/a.png"], "minItems"),
        (["--settings", '{"steps":99}'], "maximum"),
        (["--settings", "[]"], "type"),
    ],
)
def test_invalid_dynamic_inputs_never_submit(extra, message, mock_api, capsys):
    assert cli.main(["run", "vendor/model", "-p", "scene", *extra, "--json"]) == 2
    assert message in json.loads(capsys.readouterr().out)["error"]["message"]
    assert not any(r.method == "POST" for r in mock_api[0])


def test_json_arrays_and_explicit_false(mock_api, capsys):
    urls = ["https://example.com/a.png", "https://example.com/b.png"]
    assert (
        cli.main(
            [
                "price",
                "vendor/model",
                "-p",
                "scene",
                "--enabled=false",
                "--references",
                json.dumps(urls),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert json.loads(post.content)["input_params"] == {
        "prompt": "scene",
        "enabled": False,
        "references": urls,
    }


def test_model_help_is_read_only_and_shows_constraints(mock_api, capsys):
    mock_api[1].parameters.extend(
        [
            {"key": "timeout", "type": "number", "default": 10},
            {"key": "help", "type": "text", "description": "bad\x1b[31mtext"},
        ]
    )
    assert cli.main(["run", "vendor/model", "--help"]) == 0
    output = capsys.readouterr().out
    assert "--duration" in output and "[5, 10]" in output
    assert "--prompt, -p" in output and "(required)" in output
    assert "-i timeout=VALUE" in output
    assert "\x1b" not in output
    assert "Task ID:" not in output
    assert len(mock_api[0]) == 1 and mock_api[0][0].method == "GET"


def test_model_help_json_and_no_input_file_reads(mock_api, capsys):
    assert (
        cli.main(["price", "vendor/model", "--help", "--json", "--input-file", "/missing/file"])
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["model_id"] == "vendor/model"
    prompt = next(x for x in data["options"] if x["field"] == "prompt")
    assert prompt["required"] and prompt["aliases"] == ["-p"]
    assert not any(r.method == "POST" for r in mock_api[0])


@pytest.mark.parametrize("status", [401, 403, 404])
def test_model_help_and_dynamic_inputs_never_bypass_auth(status, mock_api, capsys):
    mock_api[1].schema_status = status
    for argv in (
        ["run", "vendor/model", "--help", "--json"],
        ["price", "vendor/model", "--duration", "5", "--json"],
    ):
        assert cli.main(argv) == 1
        assert json.loads(capsys.readouterr().out)["error"]["status_code"] == status
    assert len(mock_api[0]) == 2
    assert all(r.url.path.endswith("/client/models/detail") for r in mock_api[0])


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--duration", "5", "vendor/model"],
        ["price", "vendor/model", "--wait"],
        ["result", "task", "--duration", "5"],
        ["run", "vendor/model", "-x", "1"],
    ],
)
def test_dynamic_flags_are_unambiguous_and_scoped_to_model_commands(argv, monkeypatch, capsys):
    monkeypatch.setattr(cli, "make_client", lambda *_: pytest.fail("must fail before network"))
    assert cli.main([*argv, "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]


def test_non_prompt_models_and_global_options(mock_api, capsys):
    mock_api[1].parameters = [
        {"key": "text", "type": "text", "required": True},
        {"key": "voice_id", "type": "text", "required": True},
    ]
    assert (
        cli.main(
            [
                "--request-timeout",
                "10",
                "--json",
                "price",
                "vendor/model",
                "--text",
                "Hello",
                "--voice_id",
                "123",
                "--base-url",
                "https://example.invalid/custom/api/v1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert post.url.path == "/custom/api/v1/pricing/preview"
    assert json.loads(post.content)["input_params"] == {"text": "Hello", "voice_id": "123"}
    before = sum(r.method == "POST" for r in mock_api[0])
    assert cli.main(["price", "vendor/model", "-p", "scene", "--json"]) == 2
    assert "Unknown model input --prompt" in capsys.readouterr().out
    assert sum(r.method == "POST" for r in mock_api[0]) == before


def test_schema_is_fetched_again_and_defaults_are_not_injected(mock_api, capsys):
    mock_api[1].parameters.append({"key": "future", "type": "number", "default": 3})
    assert cli.main(["price", "vendor/model", "-p", "scene", "--future", "2", "--json"]) == 0
    capsys.readouterr()
    mock_api[1].parameters.pop()
    assert cli.main(["price", "vendor/model", "-p", "scene", "--future", "2", "--json"]) == 2
    assert "Unknown model input --future" in capsys.readouterr().out
    mock_api[1].parameters.append({"key": "future", "type": "number", "default": 3})
    assert cli.main(["price", "vendor/model", "-p", "scene", "--json"]) == 0
    capsys.readouterr()
    posts = [r for r in mock_api[0] if r.method == "POST"]
    assert json.loads(posts[-1].content)["input_params"] == {"prompt": "scene"}


def test_dynamic_validation_does_not_echo_input_values(mock_api, capsys):
    assert (
        cli.main(
            ["price", "vendor/model", "-p", "private prompt", "--size", "sk-cli-secret", "--json"]
        )
        == 2
    )
    output = capsys.readouterr()
    assert "private prompt" not in output.out + output.err
    assert "sk-cli-secret" not in output.out + output.err


def test_integer_nullable_and_mixed_enums_use_schema_types():
    from akool_modelhub_cli.inputs import model_inputs

    schema = {
        "properties": {
            "count": {"type": "integer"},
            "mixed": {"enum": [5, "5", False]},
            "optional": {"type": ["number", "null"]},
        }
    }
    assert model_inputs([("count", "5"), ("mixed", "5"), ("optional", "null")], schema) == {
        "count": 5,
        "mixed": "5",
        "optional": None,
    }
    with pytest.raises(ValueError, match="integer"):
        model_inputs([("count", "1.5")], schema)
    with pytest.raises(ValueError, match="requires a value"):
        model_inputs([("optional", None)], schema)


@pytest.mark.parametrize(
    "raw, expected", [(".5", 0.5), ("-.5", -0.5), ("+5", 5), ("05", 5), ("5.", 5.0)]
)
def test_command_line_number_formats(raw, expected, mock_api, capsys):
    assert cli.main(["price", "vendor/model", "-p", "scene", "--offset", raw, "--json"]) == 0
    capsys.readouterr()
    post = next(r for r in mock_api[0] if r.method == "POST")
    assert json.loads(post.content)["input_params"]["offset"] == expected


@pytest.mark.parametrize(
    "field, value", [("offset", "1e999"), ("settings", '{"steps":1,"other":1e999}')]
)
def test_overflowing_numeric_inputs_never_submit(field, value, mock_api, capsys):
    assert cli.main(["run", "vendor/model", "-p", "scene", f"--{field}", value, "--json"]) == 2
    assert "finite" in capsys.readouterr().out
    assert not any(r.method == "POST" for r in mock_api[0])
