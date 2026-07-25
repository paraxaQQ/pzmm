"""Integration test: real OpenAI SDK against a local mock chat-completions server.

Exercises the exact path every OpenAI-compatible provider (openai, gemini, xai,
deepseek, mistral, openrouter, ollama) goes through in core.ai._stream_openai:
client construction with base_url, SSE streaming, delta parsing.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core import ai


def _sse_chunk(delta: dict, finish: str | None = None) -> bytes:
    payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "test-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"


class _MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        assert body.get("model") == "test-model"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(_sse_chunk({"role": "assistant"}))
        self.wfile.write(_sse_chunk({"content": "Hello"}))
        self.wfile.write(_sse_chunk({"content": " world"}))
        # some compat endpoints send a final chunk with delta null - must not crash
        self.wfile.write(
            b'data: {"id":"chatcmpl-test","object":"chat.completion.chunk",'
            b'"created":1,"model":"test-model",'
            b'"choices":[{"index":0,"delta":null,"finish_reason":"stop"}]}\n\n'
        )
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


@pytest.fixture
def mock_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def test_openai_compatible_streaming(mock_server):
    events = list(ai._stream_openai(
        "test-key", "test-model", "you are a test",
        [{"role": "user", "content": "hi"}],
        sandbox=None, base_url=mock_server, label="MockProvider",
    ))
    text = "".join(e["text"] for e in events if e["type"] == "text")
    assert text == "Hello world"


def test_stream_chat_routes_ollama_without_key(mock_server, monkeypatch):
    # ollama is key_optional: stream_chat must not raise on an empty key
    monkeypatch.setitem(ai.PROVIDERS["ollama"], "base_url", mock_server)
    events = list(ai.stream_chat(
        "ollama", "", "test-model", "you are a test",
        [{"role": "user", "content": "hi"}],
    ))
    text = "".join(e["text"] for e in events if e["type"] == "text")
    assert text == "Hello world"


def test_stream_chat_requires_key_for_key_required_providers():
    with pytest.raises(ai.AIError, match="No API key"):
        list(ai.stream_chat("deepseek", "", "deepseek-v4-flash", "sys", []))


def test_stream_chat_unknown_provider():
    with pytest.raises(ai.AIError, match="Unknown provider"):
        list(ai.stream_chat("nope", "k", "m", "sys", []))
