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
                        "parameters": [{"key": "prompt", "type": "text", "required": True}],
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
            ["price", "smoke/model", "-p", "test", "--json"],
            ["run", "smoke/model", "-p", "test", "--request-id", "binary-task", "--wait", "--json"],
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

    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    print("Standalone CLI: 7 commands passed")


if __name__ == "__main__":
    main()
