"""Terminal entry point. stdout is one JSON result in --json mode; diagnostics use stderr."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from akool_modelhub_sdk import AsyncModelHub, convert_schema, validate_id
from akool_modelhub_sdk.errors import (
    ModelHubError,
    SubmissionUnknownError,
    TaskCancelledError,
    TaskFailedError,
    TaskWaitTimeoutError,
)
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from akool_modelhub_cli.config import (
    DEFAULT_BASE_URL,
    clear_credentials,
    config_path,
    read_config,
    resolve_config,
    validate_base_url,
    write_config,
)
from akool_modelhub_cli.inputs import (
    UsageError,
    format_help,
    help_data,
    model_inputs,
    parse_arguments,
    reject_constant,
)

VERSION = "0.2.0"
MAX_INPUT_BYTES = 1024 * 1024


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise UsageError(message)


@dataclass
class Operation:
    request_id: str | None = None
    task_uuid: str | None = None
    model_id: str | None = None
    api_key: str | None = None


def build_parser() -> Parser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print one JSON value to stdout; diagnostics go to stderr",
    )
    common.add_argument(
        "--base-url",
        default=argparse.SUPPRESS,
        help="API root including /api/v1; overrides environment and local configuration",
    )
    common.add_argument(
        "--request-timeout",
        type=float,
        default=argparse.SUPPRESS,
        help="HTTP operation deadline in seconds (default: 90)",
    )
    common.add_argument("--version", action="version", version=f"AKOOL Model Hub CLI {VERSION}")
    parser = Parser(
        prog="akool-mh",
        description="AKOOL Model Hub CLI: models → schema → price → run → result",
        parents=[common],
    )
    parser.set_defaults(json=False, base_url=None, request_timeout=90.0)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    parser.command_parsers = commands.choices
    for name, help_text in (
        ("login", "Validate and save your Model Hub API key (interactive, no generation)"),
        ("logout", "Remove the locally stored Model Hub key; keep the API root"),
        ("status", "Verify credentials and API connectivity without generating media"),
    ):
        commands.add_parser(name, help=help_text, parents=[common])
    upgrade = commands.add_parser(
        "upgrade",
        help="Update the standalone binary without changing credentials",
        parents=[common],
    )
    upgrade.add_argument("--target-version", help="Install an exact release version")
    models = commands.add_parser(
        "models", help="Search models requestable with the current API key", parents=[common]
    )
    models.add_argument("query", nargs="?")
    models.add_argument("--type", dest="task_type", help="Task type from the model catalog")
    models.add_argument("--tags", help="Comma-separated tags")
    models.add_argument("--limit", type=int, default=20)
    models.add_argument("--skip", type=int, default=0)
    schema = commands.add_parser(
        "schema", help="Inspect a model's inputs, outputs and examples", parents=[common]
    )
    schema.add_argument("model_id")
    for name in ("price", "run"):
        command = commands.add_parser(
            name,
            parents=[common],
            help="Preview the price"
            if name == "price"
            else "Submit one billable task; add --wait to wait for its result",
            epilog=(
                "Model inputs: --FIELD VALUE (exact schema names). "
                "Use this command with MODEL_ID --help for model-specific options. "
                "Precedence: file → model flags (including -p) → -i."
            ),
        )
        command.add_argument("model_id")
        command.add_argument(
            "--input-file", help="JSON object file; '-' reads stdin. Media paths are not uploaded."
        )
        command.add_argument("-p", "--prompt", help="Shortcut for the model's prompt input")
        command.add_argument(
            "-i",
            "--input",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="Set an exact input field; JSON values are typed, other values are strings",
        )
        if name == "run":
            command.add_argument(
                "--request-id",
                help="Stable task ID (max 36 characters). Reuse only with identical input.",
            )
            command.add_argument("--webhook", help="HTTPS callback URL")
            command.add_argument(
                "--wait",
                action="store_true",
                help="Wait for the submitted task to reach a terminal state",
            )
            command.add_argument(
                "--timeout", type=float, default=600, help="Wait deadline in seconds (default: 600)"
            )
    result = commands.add_parser(
        "result",
        help="Read or wait for an existing task; never creates a new one",
        parents=[common],
    )
    result.add_argument("task_uuid")
    result.add_argument("--wait", action="store_true")
    result.add_argument("--timeout", type=float, default=600)
    history = commands.add_parser(
        "history", help="List tasks for this account (across its keys)", parents=[common]
    )
    history.add_argument("--model", dest="model_id")
    history.add_argument("--status")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--skip", type=int, default=0)
    return parser


def read_input(args, *, base_only=False) -> dict[str, Any]:
    result = {}
    if args.input_file:
        if args.input_file == "-":
            raw = sys.stdin.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(args.input_file).open("rb") as source:
                raw = source.read(MAX_INPUT_BYTES + 1).decode("utf-8")
        if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
            raise UsageError("Input JSON exceeds 1 MiB")
        try:
            result = json.loads(raw, parse_constant=reject_constant)
        except json.JSONDecodeError as exc:
            raise UsageError(
                f"Invalid input JSON at line {exc.lineno}, column {exc.colno}"
            ) from None
        if not isinstance(result, dict):
            raise UsageError("Input JSON must be an object")
    if args.prompt is not None:
        result["prompt"] = args.prompt
    for item in [] if base_only else args.input:
        key, separator, value = item.partition("=")
        if not separator or not key or any(ord(c) < 32 for c in key):
            raise UsageError("Use -i KEY=VALUE with a nonempty field name")
        try:
            parsed = json.loads(value, parse_constant=reject_constant)
        except json.JSONDecodeError:
            parsed = value
        result[key] = parsed
    json.dumps(result, allow_nan=False)
    return result


def make_client(configuration, args):
    return AsyncModelHub(
        api_key=configuration.api_key, base_url=configuration.base_url, timeout=args.request_timeout
    )


async def verify_credentials(client) -> dict:
    capabilities = await client.capabilities(refresh=True)
    if capabilities.contract_version is None:
        # A missing capabilities endpoint says nothing about credential validity.
        await client.tasks.list(limit=1)
    return capabilities.model_dump(exclude={"request_id"})


def task_output(task, model_id: str | None = None) -> dict:
    data = task.model_dump(
        mode="json",
        include={
            "task_uuid",
            "request_id",
            "model_id",
            "status",
            "output",
            "amount",
            "error_message",
            "created_at",
            "completed_at",
            "estimated_time",
        },
    )
    data.setdefault("model_id", model_id)
    data.setdefault("output", None)
    data["error"] = None
    return data


async def login(args, operation: Operation) -> dict:
    if not sys.stdin.isatty():
        raise UsageError("login requires an interactive terminal; use AKOOL_MODELHUB_API_KEY in CI")
    saved = read_config()
    base = (
        args.base_url
        or os.getenv("AKOOL_MODELHUB_BASE_URL")
        or saved.get("base_url")
        or DEFAULT_BASE_URL
    )
    base = validate_base_url(base)
    key = getpass.getpass("Model Hub API key: ", stream=sys.stderr)
    if not key or any(c in key for c in "\r\n"):
        raise UsageError("Invalid API key")
    operation.api_key = key
    from akool_modelhub_cli.config import Configuration

    async with make_client(Configuration(key, base, "interactive"), args) as client:
        await verify_credentials(client)
    write_config({"api_key": key, "base_url": base})
    return {
        "authenticated": True,
        "base_url": base,
        "config_path": str(config_path()),
        "environment_override": bool(os.getenv("AKOOL_MODELHUB_API_KEY")),
    }


async def execute(args, operation: Operation) -> tuple[dict, int]:
    if not math.isfinite(args.request_timeout) or args.request_timeout <= 0:
        raise UsageError("--request-timeout must be positive and finite")
    if hasattr(args, "timeout") and (not math.isfinite(args.timeout) or args.timeout <= 0):
        raise UsageError("--timeout must be positive and finite")
    if args.command == "upgrade":
        from .upgrade import upgrade_binary

        return await asyncio.to_thread(upgrade_binary, version=args.target_version), 0
    if args.command == "login":
        return await login(args, operation), 0
    if args.command == "logout":
        clear_credentials()
        return {
            "local_credentials_removed": True,
            "environment_key_present": bool(os.getenv("AKOOL_MODELHUB_API_KEY")),
        }, 0
    # Local validation precedes any network call.
    inputs = (
        read_input(args, base_only=True)
        if args.command in ("run", "price") and not getattr(args, "model_help", False)
        else None
    )
    overrides = (
        read_input(argparse.Namespace(input_file=None, prompt=None, input=args.input))
        if inputs is not None
        else {}
    )
    if args.command in ("run", "price"):
        validate_id(args.model_id, model=True)
    if args.command == "run":
        validate_id(args.model_id, model=True)
        if args.request_id is not None:
            validate_id(args.request_id)
        if args.webhook:
            from urllib.parse import urlsplit

            url = urlsplit(args.webhook)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise UsageError("--webhook must be an HTTPS URL without credentials")
    configuration = resolve_config(base_url=args.base_url)
    operation.api_key = configuration.api_key
    async with make_client(configuration, args) as client:
        if args.command == "status":
            capabilities = await verify_credentials(client)
            return {
                "authenticated": True,
                "base_url": configuration.base_url,
                "credential_source": configuration.credential_source,
                "capabilities": capabilities,
            }, 0
        if args.command == "models":
            page = await client.models.list(
                search=args.query,
                task_type=args.task_type,
                tags=args.tags.split(",") if args.tags else None,
                limit=args.limit,
                skip=args.skip,
                refresh=True,
            )
            return page.model_dump(mode="json"), 0
        if args.command == "history":
            page = await client.tasks.list(
                model_id=args.model_id, status=args.status, limit=args.limit, skip=args.skip
            )
            return {
                "items": [task_output(item) for item in page.items],
                "total": page.total,
                "skip": page.skip,
                "limit": page.limit,
                "visibility": "account",
            }, 0
        if args.command == "schema":
            model = await client.models.get(args.model_id, refresh=True)
            schema = convert_schema(model)
            return {**schema.model_dump(mode="json"), "examples": model.examples}, 0
        if args.command in ("price", "run"):
            schema = await client.models.schema(args.model_id, refresh=True)
            if getattr(args, "model_help", False):
                return help_data(
                    args.model_id, args.command, schema.input_schema, args.reserved_inputs
                ), 0
            inputs.update(
                model_inputs(
                    getattr(args, "model_inputs", []), schema.input_schema, overridden=overrides
                )
            )
            # -i is the final override, including reserved or otherwise unusual field names.
            inputs.update(overrides)
            try:
                Draft202012Validator(schema.input_schema, format_checker=FormatChecker()).validate(
                    inputs
                )
            except ValidationError as exc:
                path = ".".join(str(part) for part in exc.absolute_path) or "input"
                # Schema validation messages can contain full input or embedded credentials.
                raise UsageError(
                    f"Invalid {path}: violates {exc.validator}; inspect akool-mh schema {args.model_id}"
                ) from None
            if args.command == "price":
                price = await client.pricing.preview(args.model_id, input=inputs)
                return {**price.model_dump(mode="json"), "binding": False}, 0
            operation.request_id = args.request_id or str(uuid4())
            operation.task_uuid, operation.model_id = operation.request_id, args.model_id
            print(f"Task ID: {operation.task_uuid}", file=sys.stderr, flush=True)
            task = await client.tasks.create(
                args.model_id,
                input=inputs,
                request_id=operation.request_id,
                webhook_url=args.webhook,
            )
            operation.task_uuid = task.task_uuid
            if args.wait:
                task = await client.tasks.wait(task.task_uuid, timeout=args.timeout)
            return task_output(task, args.model_id), 0
        operation.task_uuid = args.task_uuid
        validate_id(args.task_uuid)
        task = (
            await client.tasks.wait(args.task_uuid, timeout=args.timeout)
            if args.wait
            else await client.tasks.get(args.task_uuid)
        )
        return task_output(task), 3 if task.status in ("failed", "cancelled") else 0


def redact(message: str, operation: Operation) -> str:
    for secret in (
        operation.api_key,
        os.getenv("AKOOL_MODELHUB_API_KEY"),
    ):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message


def error_output(exc: Exception, operation: Operation) -> tuple[dict, int]:
    code = 1
    if isinstance(exc, (ValueError, OSError)):
        code = 2
    if isinstance(exc, (TaskFailedError, TaskCancelledError)):
        code = 3
    if isinstance(exc, TaskWaitTimeoutError):
        code = 4
    if isinstance(exc, SubmissionUnknownError):
        code = 5
    task = getattr(exc, "task", None)
    data = task_output(task, operation.model_id) if task is not None else {}
    data.update(
        {
            "request_id": getattr(exc, "request_id", None) or operation.request_id,
            "task_uuid": getattr(exc, "candidate_task_uuid", None)
            or getattr(exc, "task_uuid", None)
            or operation.task_uuid,
            "error": {
                "code": getattr(exc, "code", "invalid_arguments" if code == 2 else "client_error"),
                "message": redact(str(exc), operation),
                "status_code": getattr(exc, "status_code", None),
            },
        }
    )
    return data, code


def emit(data: dict, as_json: bool, operation: Operation) -> None:
    # Pretty JSON is also the human-readable representation; no ambiguous output heuristics.
    print(
        redact(
            json.dumps(data, ensure_ascii=False, allow_nan=False, indent=None if as_json else 2),
            operation,
        )
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    operation = Operation()
    as_json = "--json" in argv
    try:
        args = parse_arguments(build_parser(), argv)
        as_json = args.json
        data, exit_code = asyncio.run(execute(args, operation))
        if getattr(args, "model_help", False) and not as_json:
            print(redact(args.command_help + "\n" + format_help(data), operation))
            return exit_code
    except KeyboardInterrupt:
        data, exit_code = (
            {
                "task_uuid": operation.task_uuid,
                "request_id": operation.request_id,
                "error": {
                    "code": "interrupted",
                    "message": "Stopped locally. Query the original task ID before resubmitting.",
                },
            },
            130,
        )
    except (ModelHubError, ValueError, OSError) as exc:
        data, exit_code = error_output(exc, operation)
    emit(data, as_json, operation)
    return exit_code


def entrypoint():
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
