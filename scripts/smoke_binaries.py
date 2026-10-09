"""Exercise packaged CLI via localhost-only fake API; no real keys or model calls."""

import argparse
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    submitted = []
    task = {
        "task_uuid": "binary-task",
        "model_id": "smoke/model",
        "status": "completed",
        "output": {"image_url": "https://example.invalid/result.png"},
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, data, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Request-Id", "query-trace")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def do_GET(self):
            assert self.headers.get("Authorization") == "Bearer sk-binary-test"
            path = self.path.split("?")[0]
            assert path not in ("/api/v1/models", "/api/v1/models/detail")
            if path.endswith("capabilities"):
                self.send(
                    {
                        "contract_version": "test",
                        "run_idempotency_v1": True,
                        "idempotency_header": "X-Request-Id",
                    }
                )
            elif path.endswith("models/detail"):
                self.send(
                    {
                        "model_id": "smoke/model",
                        "parameters": [
                            {"key": "prompt", "type": "text", "required": True},
                            {
                                "key": "duration",
                                "type": "select",
                                "options": [{"value": 5}, {"value": 10}],
                            },
                            {"key": "enabled", "type": "boolean"},
                            {"key": "references", "type": "image_upload_group", "min_count": 2},
                            {"key": "timeout", "type": "number"},
                        ],
                        "examples": [],
                    }
                )
            elif path.endswith("/models"):
                self.send({"total": 1, "items": [{"model_id": "smoke/model"}]})
            elif path.endswith("/run/tasks"):
                self.send({"total": 1, "items": [task]})
            elif "/run/tasks/" in path:
                self.send({**task, "task_uuid": path.rsplit("/", 1)[-1]})
            else:
                self.send({}, 404)

        def do_POST(self):
            assert self.headers.get("Authorization") == "Bearer sk-binary-test"
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path.endswith("pricing/preview"):
                self.send({"list_price": 1, "final_price": 1, "discount_rate": 1, "you_save": 0})
            else:
                submitted.append((self.headers["X-Request-Id"], body))
                self.send(
                    {"task_uuid": self.headers["X-Request-Id"], "status": "pending", "amount": 1}
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    env = {
        **os.environ,
        "AKOOL_MODELHUB_API_KEY": "sk-binary-test",
        "AKOOL_MODELHUB_BASE_URL": f"http://127.0.0.1:{server.server_port}/api/v1",
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    suffix = ".exe" if os.name == "nt" else ""
    cli = str((args.directory / f"akool-mh{suffix}").resolve())
    try:
        for command in [
            ["--json", "status"],
            ["models", "image", "--json"],
            ["schema", "smoke/model", "--json"],
            ["price", "smoke/model", "--prompt", "test", "--duration", "5", "--json"],
            [
                "run",
                "smoke/model",
                "--prompt",
                "test",
                "--duration=5",
                "--enabled",
                "--references",
                "https://example.com/a.png",
                "--references",
                "https://example.com/b.png",
                "--timeout",
                "5",
                "-i",
                "timeout=8",
                "--request-id",
                "binary-task",
                "--wait",
                "--json",
            ],
            ["result", "binary-task", "--json"],
            ["history", "--json"],
        ]:
            result = subprocess.run(
                [cli, *command], env=env, check=False, text=True, capture_output=True, timeout=30
            )
            assert result.returncode == 0, (command, result.stdout, result.stderr)
            assert isinstance(json.loads(result.stdout), dict)
            assert "sk-binary-test" not in result.stdout + result.stderr
        assert len(submitted) == 1
        assert submitted[0][1]["input"] == {
            "prompt": "test",
            "duration": 5,
            "enabled": True,
            "timeout": 8,
            "references": ["https://example.com/a.png", "https://example.com/b.png"],
        }
        for command, code, fragment in [
            (["run", "smoke/model", "--help"], 0, "--duration"),
            (["price", "smoke/model", "--help", "--json"], 0, '"options"'),
            (
                ["run", "smoke/model", "--prompt", "test", "--duraton", "5", "--json"],
                2,
                "Did you mean --duration",
            ),
            (["run", "smoke/model", "--prompt", "test", "--duration", "7", "--json"], 2, "enum"),
        ]:
            result = subprocess.run(
                [cli, *command], env=env, capture_output=True, text=True, timeout=30
            )
            assert result.returncode == code, (command, result.stdout, result.stderr)
            assert fragment in result.stdout
        assert len(submitted) == 1, "Help or invalid inputs must never submit tasks"

    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    print("Standalone CLI: 7 commands and 4 dynamic-input/help checks passed")


if __name__ == "__main__":
    main()
