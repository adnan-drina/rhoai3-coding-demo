"""Scripted fake OpenAI-compatible chat-completions provider (no real model).

Every POST /v1/chat/completions is answered from a script: a list of
``("tool", name, arguments_dict)`` or ``("text", content)`` steps. When the
script is exhausted the last step repeats forever, which models a worker that
keeps issuing the same tool call. Supports both ``stream: true`` (SSE) and
plain JSON responses. Records every request body so tests can count model
requests and inspect what the worker sent.

Loopback only; no network model is ever contacted.
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeProvider:
    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        handler = self._make_handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def chat_request_count(self) -> int:
        with self._lock:
            return sum(1 for r in self.requests if r.get("_path", "").endswith("/chat/completions"))

    def _next_step(self):
        with self._lock:
            n = sum(1 for r in self.requests if r.get("_path", "").endswith("/chat/completions"))
        idx = min(n - 1, len(self.script) - 1)
        return self.script[idx]

    def _make_handler(self):
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _send_json(self, obj, status=200):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    self._send_json({"object": "list", "data": [
                        {"id": "fake-model", "object": "model", "owned_by": "test",
                         "context_length": 131072},
                    ]})
                else:
                    self._send_json({"error": "not found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    body = {}
                body["_path"] = self.path
                with provider._lock:
                    provider.requests.append(body)
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self._send_json({"error": "unsupported"}, 404)
                    return
                step = provider._next_step()
                if step[0] == "tool":
                    _, name, args = step
                    call = {
                        "index": 0,
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                    message = {"role": "assistant", "content": None, "tool_calls": [call]}
                    finish = "tool_calls"
                else:
                    message = {"role": "assistant", "content": step[1]}
                    finish = "stop"
                usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
                created = 1_700_000_000
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    delta = {"role": "assistant"}
                    if "tool_calls" in message:
                        delta["tool_calls"] = message["tool_calls"]
                    else:
                        delta["content"] = message["content"]
                    chunks = [
                        {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": created,
                         "model": "fake-model",
                         "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                        {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": created,
                         "model": "fake-model",
                         "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                         "usage": usage},
                    ]
                    for chunk in chunks:
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                else:
                    self._send_json({
                        "id": "chatcmpl-fake", "object": "chat.completion", "created": created,
                        "model": "fake-model",
                        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                        "usage": usage,
                    })

        return Handler
