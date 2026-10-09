"""Schema-driven model options, kept separate from the CLI's own controls."""

from __future__ import annotations

import difflib
import json
import math
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class UsageError(ValueError):
    pass


def reject_constant(value: str):
    raise UsageError(f"Non-finite JSON number is not allowed: {value}")


def option_parts(token, actions):
    """Recognize exact options only, including -pTEXT, -iKEY=VALUE and --key=value."""
    if token.startswith("--"):
        key, separator, value = token.partition("=")
        return key, value if separator else None
    if token in actions:
        return token, None
    for key in ("-p", "-i"):
        if token.startswith(key) and key in actions:
            return key, token[len(key) :].removeprefix("=")
    return token, None


def parse_arguments(parser, argv):
    """Separate model values before argparse can interpret them as CLI controls.

    The model ID must precede dynamic flags. Generic help stays offline, while
    `run MODEL --help` resolves the model schema using the caller's credentials.
    """
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in parser.command_parsers:
            break
        key, attached = option_parts(token, parser._option_string_actions)
        action = parser._option_string_actions.get(key)
        if action is None or key in ("-h", "--help", "--version"):
            return parser.parse_args(argv)
        index += 1
        if action.nargs != 0 and attached is None:
            index += 1
    if index >= len(argv) or argv[index] not in ("run", "price"):
        return parser.parse_args(argv)

    command = argv[index]
    subparser = parser.command_parsers[command]
    actions = subparser._option_string_actions
    reserved = {
        key[2:]
        for name in ("run", "price")
        for key in parser.command_parsers[name]._option_string_actions
        if key.startswith("--") and key != "--prompt"
    }
    filtered = argv[: index + 1]
    values = []
    model_id = None
    help_requested = False
    index += 1
    while index < len(argv):
        token = argv[index]
        key, attached = option_parts(token, actions)
        if key in ("--help", "-h") and attached is None:
            help_requested = True
            index += 1
            continue
        if key in ("-p", "--prompt"):
            value = attached
            if value is None and index + 1 < len(argv):
                following = argv[index + 1]
                if not following.startswith("-") or re.match(r"^-(?:\d|\.\d)", following):
                    value = following
                    index += 1
            values.append(("prompt", value))
            index += 1
            continue
        action = actions.get(key)
        if action is not None:
            consumed = [token]
            value = attached
            if action.nargs != 0 and value is None:
                if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
                    raise UsageError(f"{key} requires a value; use {key}=VALUE for leading dashes")
                value = argv[index + 1]
                consumed.append(value)
                index += 1
            filtered.extend(consumed)
        elif token.startswith("--"):
            if model_id is None:
                raise UsageError("Put MODEL_ID before model options: run MODEL_ID --FIELD VALUE")
            field = key[2:]
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", field) or field in reserved:
                raise UsageError(
                    f"{key} is not a model option here; use -i FIELD=VALUE for model inputs"
                )
            value = attached
            if value is None and index + 1 < len(argv):
                following = argv[index + 1]
                if not following.startswith("-") or re.match(r"^-(?:\d|\.\d)", following):
                    value = following
                    index += 1
            values.append((field, value))
        elif not token.startswith("-") and model_id is None:
            model_id = token
            filtered.append(token)
        else:
            raise UsageError("Unexpected argument; use --FIELD VALUE or -i KEY=VALUE")
        index += 1

    if help_requested and model_id is None:
        # argparse prints local command help and exits without reading configuration.
        return parser.parse_args([*filtered, "--help"])
    args = parser.parse_args(filtered)
    args.model_inputs = values
    args.model_help = help_requested
    args.reserved_inputs = reserved
    args.command_help = subparser.format_help()
    return args


def validator(schema):
    return Draft202012Validator(schema, format_checker=FormatChecker())


def is_boolean(schema):
    kind = schema.get("type")
    return (
        kind == "boolean"
        or isinstance(kind, list)
        and "boolean" in kind
        or any(type(value) is bool for value in schema.get("enum", []))
        or any(is_boolean(part) for part in schema.get("anyOf", []) if isinstance(part, dict))
    )


def parse_value(field: str, raw: str | None, schema: dict) -> Any:
    check = validator(schema)
    if raw is None:
        if is_boolean(schema) and check.is_valid(True):
            return True
        raise UsageError(f"--{field} requires a value")
    # Prefer a valid string so numeric-looking strings and string enum members stay exact.
    if check.is_valid(raw):
        return raw
    try:
        value = json.loads(raw, parse_constant=reject_constant)
    except (ValueError, TypeError):
        value = raw
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw):
            value = int(raw) if re.fullmatch(r"[+-]?\d+", raw) else float(raw)
    if isinstance(value, float) and not math.isfinite(value):
        raise UsageError(f"Invalid --{field}: expected a finite number")
    error = next(check.iter_errors(value), None)
    if error is not None:
        expected = schema.get(
            "type", "one of the allowed values" if "enum" in schema else "the schema"
        )
        raise UsageError(f"Invalid --{field}: expected {expected}; violates {error.validator}")
    return value


def model_inputs(values, schema: dict, *, overridden=()) -> dict[str, Any]:
    """Convert long options; repeated arrays append, repeated scalars use the last value."""
    properties = schema.get("properties", {})
    grouped = {}
    for field, raw in values:
        if field not in properties:
            matches = difflib.get_close_matches(field, properties, n=1, cutoff=0.65)
            hint = f" Did you mean --{matches[0]}?" if matches else ""
            raise UsageError(f"Unknown model input --{field}.{hint} Use run MODEL_ID --help.")
        if field not in overridden:
            grouped.setdefault(field, []).append(raw)
    result = {}
    for field, entries in grouped.items():
        spec = properties[field]
        if spec.get("type") == "array":
            for raw in entries:
                if raw is None:
                    raise UsageError(f"--{field} requires a value")
                try:
                    decoded = json.loads(raw, parse_constant=reject_constant)
                except ValueError:
                    decoded = raw
                if isinstance(decoded, list):
                    items = decoded
                else:
                    items = [parse_value(field, raw, spec.get("items", {}))]
                result.setdefault(field, []).extend(items)
        else:
            result[field] = parse_value(field, entries[-1], spec)
    # Validate arrays only after collection, so minItems/maxItems apply to the whole list.
    for field, value in result.items():
        error = next(validator(properties[field]).iter_errors(value), None)
        if error is not None:
            raise UsageError(f"Invalid --{field}: violates {error.validator}")
    try:
        json.dumps(result, allow_nan=False)
    except ValueError:
        raise UsageError("Model inputs must contain finite JSON values") from None
    return result


def help_data(model_id: str, command: str, schema: dict, reserved: set[str]) -> dict:
    options = []
    required = schema.get("required", [])
    for field, spec in schema.get("properties", {}).items():
        direct = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", field)) and field not in reserved
        options.append(
            {
                "field": field,
                "option": f"--{field}" if direct else None,
                "aliases": ["-p"] if field == "prompt" else [],
                "input_syntax": f"-i {field}=VALUE",
                "required": field in required,
                "schema": spec,
            }
        )
    return {
        "model_id": model_id,
        "command": command,
        "options": options,
        "precedence": ["input-file", "model-options", "input"],
    }


def format_help(data: dict) -> str:
    def safe(value):
        # JSON encoding keeps terminal control characters in backend descriptions inert.
        return json.dumps(value, ensure_ascii=False)

    lines = [f"Model inputs for {safe(data['model_id'])}:"]
    for option in data["options"]:
        spec = option["schema"]
        syntax = safe(option["option"] or option["input_syntax"])[1:-1]
        kind = spec.get("type", "enum" if "enum" in spec else "value")
        note = " (required)" if option["required"] else ""
        alias = ", -p" if option["aliases"] else ""
        lines.append(f"  {syntax}{alias}  [{kind}]{note}")
        if not option["option"]:
            lines.append("    Use -i for this field; its name is reserved or unsuitable as a flag.")
        for key in ("description", "enum", "default", "minimum", "maximum", "minItems", "maxItems"):
            if key in spec:
                lines.append(f"    {key}: {safe(spec[key])}")
    if not data["options"]:
        lines.append("  No model input fields are advertised; inspect the model's schema.")
    lines.extend(
        [
            "",
            "Booleans: --FIELD or --FIELD true/false. Arrays: repeat --FIELD VALUE or pass a JSON array.",
            "Use --FIELD=VALUE when a value starts with '-'. Objects accept JSON values.",
            "Precedence: --input-file < model flags (including -p) < -i KEY=VALUE.",
            "CLI controls keep their meanings; use -i for model fields with the same names.",
        ]
    )
    return "\n".join(lines)
