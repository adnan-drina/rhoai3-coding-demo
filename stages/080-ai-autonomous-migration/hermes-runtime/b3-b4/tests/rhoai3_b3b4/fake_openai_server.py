"""Scripted fake OpenAI-compatible chat-completions provider (loopback only).

Extends the B11 fake with the failure shapes B3/B4 need. Every POST
/v1/chat/completions consumes the next script step; the last step repeats
forever. Steps:

  ("tool", name, args_dict[, usage_dict])    complete tool call, finish_reason=tool_calls
  ("text", content)                          plain answer, finish_reason=stop
  ("truncated_tool", name, partial_args_str) stream ends mid tool-call arguments with
                                             finish_reason=length (the vLLM max_tokens shape)
  ("http", status, headers_dict, body_dict)  non-200 response (e.g. 429 + Retry-After)
  ("drop",)                                  200 + SSE headers, then close: a dropped stream
  ("stall", seconds)                         200 + SSE headers, silence, then close: a stalled stream

A trailing dict on a tool/text step may carry: prompt_tokens / completion_tokens
(reported usage), no_usage=True (terminal response without usage), and
usage_frames=[{prompt_tokens, completion_tokens}, ...] (cumulative usage
frames streamed before the terminal chunk).

``usage.prompt_tokens`` is estimated from the request size (chars/4) so
Hermes' usage-driven context logic behaves as it would against a server.
Every request body is recorded with its arrival time (``_t``, monotonic).
No real model and no network model are ever contacted.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeProvider:
    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
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

    def chat_requests(self) -> list[dict]:
        with self._lock:
            return [r for r in self.requests if r.get("_path", "").endswith("/chat/completions")]

    def _make_handler(self):
        provider = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send_json(self, obj, status=200, headers=None):
                body = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, str(v))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    self._send_json({"object": "list", "data": [
                        {"id": "fake-model", "object": "model", "owned_by": "test"}]})
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
                body["_t"] = time.monotonic()
                body["_headers"] = {k.lower(): v for k, v in self.headers.items()}
                with provider._lock:
                    provider.requests.append(body)
                    n = sum(1 for r in provider.requests if r.get("_path", "").endswith("/chat/completions"))
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self._send_json({"error": "unsupported"}, 404)
                    return
                step = provider.script[min(n - 1, len(provider.script) - 1)]
                if step[0] == "stall":
                    # 200 + SSE headers, then silence for step[1] seconds, then
                    # close: an already-sent request whose stream stalls.
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.flush()
                    time.sleep(float(step[1]))
                    self.close_connection = True
                    return
                if step[0] == "drop":
                    # 200 + SSE headers, then the connection closes with no
                    # event: a dropped stream the client must reconnect.
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.flush()
                    self.close_connection = True
                    return
                if step[0] == "http":
                    _, status, headers, payload = step
                    self._send_json(payload, status=status, headers=headers)
                    return
                prompt_tokens = max(1, len(raw) // 4)
                completion_tokens = 10
                # Optional trailing dict on a step overrides the reported usage,
                # e.g. ("tool", name, args, {"prompt_tokens": 190000}).
                extras = step[-1] if isinstance(step[-1], dict) and step[0] in ("tool", "text") and len(step) > (3 if step[0] == "tool" else 2) else {}
                prompt_tokens = int(extras.get("prompt_tokens", prompt_tokens))
                completion_tokens = int(extras.get("completion_tokens", completion_tokens))
                usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                         "total_tokens": prompt_tokens + completion_tokens}
                call_id = f"call_{uuid.uuid4().hex[:12]}"
                if step[0] == "tool":
                    delta = {"role": "assistant", "tool_calls": [{
                        "index": 0, "id": call_id, "type": "function",
                        "function": {"name": step[1], "arguments": json.dumps(step[2])}}]}
                    message = {"role": "assistant", "content": None, "tool_calls": delta["tool_calls"]}
                    finish = "tool_calls"
                elif step[0] == "truncated_tool":
                    delta = {"role": "assistant", "tool_calls": [{
                        "index": 0, "id": call_id, "type": "function",
                        "function": {"name": step[1], "arguments": step[2]}}]}
                    message = {"role": "assistant", "content": None, "tool_calls": delta["tool_calls"]}
                    finish = "length"
                    usage["completion_tokens"] = int(body.get("max_tokens") or 8192)
                    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
                else:
                    delta = {"role": "assistant", "content": step[1]}
                    message = {"role": "assistant", "content": step[1]}
                    finish = "stop"
                created = 1_700_000_000
                if extras.get("no_usage"):
                    usage = None                      # terminal response without usage
                body["_usage_sent"] = usage           # what this response reported
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    first = {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": created,
                             "model": body.get("model", "fake-model"),
                             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
                    chunks = [first]
                    # Optional cumulative usage frames before the terminal one.
                    for frame in extras.get("usage_frames", []):
                        chunks.append({"id": "chatcmpl-fake", "object": "chat.completion.chunk",
                                       "created": created, "model": body.get("model", "fake-model"),
                                       "choices": [], "usage": {**frame, "total_tokens":
                                           frame["prompt_tokens"] + frame["completion_tokens"]}})
                    last = {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": created,
                            "model": body.get("model", "fake-model"),
                            "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]}
                    if usage is not None:
                        last["usage"] = usage
                    chunks.append(last)
                    for chunk in chunks:
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    self.close_connection = True
                else:
                    self._send_json({
                        "id": "chatcmpl-fake", "object": "chat.completion", "created": created,
                        "model": body.get("model", "fake-model"),
                        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                        **({"usage": usage} if usage is not None else {}),
                    })

        return Handler
