#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  uv venv --python "${PYTHON_VERSION:-3.12}" .venv
fi
packages=(-e . --group dev)
if [ -n "${MODELHUB_SDK_WHEEL:-}" ]; then
  packages+=("$MODELHUB_SDK_WHEEL")
fi
uv pip install --python .venv/bin/python "${packages[@]}"
.venv/bin/python -m pytest
.venv/bin/ruff check src tests scripts
uv build --out-dir dist
