"""S1-mini through host Ollama, retaining the HF tokenizer and exact non-thinking prompt.

The synchronous Loaded protocol runs in S1MiniEngine's worker threads. No torch weights
are loaded here. Raw generation avoids Ollama chat-template/default penalty differences.
"""
from __future__ import annotations

import json
import http.client
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator

from engine import DEFAULT_MODEL, EngineError, S1MiniEngine

DEFAULT_OLLAMA_MODEL = "s1-mini:f16"
TOKENIZER_REVISION = "88f6b15896c73bbb13a3b596e0afe8ea0d5150b4"


def _call(url: str, path: str, body: dict[str, Any] | None, timeout: float):
    request = urllib.request.Request(
        f"{url}{path}", data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        with error:
            detail = error.read(2000).decode("utf-8", "replace")
        raise EngineError(f"Ollama answered {error.code}: {detail}", 400 if error.code == 400 else None) from None
    except (OSError, http.client.HTTPException) as error:
        raise EngineError(f"Ollama at {url} is unreachable: {error}") from None


def _read_json(response) -> dict[str, Any]:
    """Read failures use the same public engine error contract as connection failures."""
    try:
        return OllamaLoaded._decode(response.read())
    except (OSError, http.client.HTTPException) as error:
        raise EngineError(f"Ollama response failed: {error}") from None


def load_tokenizer(source: str):
    """Only the small tokenizer download; same source and token counting as torch."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(source, revision=TOKENIZER_REVISION if source == DEFAULT_MODEL else None)


class OllamaLoaded:
    """Loaded.count/stream backed by Ollama's raw /api/generate NDJSON protocol."""

    def __init__(self, url: str, model: str, tokenizer: Any, load_timeout: float = 300.0,
                 threads: Callable[[], int | None] = lambda: None) -> None:
        self.url, self.model = url.rstrip("/"), model
        self.tokenizer, self._threads = tokenizer, threads
        with _call(self.url, "/api/generate", {"model": model, "prompt": "", "stream": False,
                                             "options": self._options()}, load_timeout) as response:
            _read_json(response)

    def count(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    def _options(self) -> dict[str, Any]:
        options = {"temperature": 0, "repeat_penalty": 1.0, "num_ctx": 4096, "num_gpu": 0}
        if count := self._threads():
            options["num_thread"] = count
        return options

    @staticmethod
    def _decode(raw: bytes) -> dict[str, Any]:
        try:
            piece = json.loads(raw)
            if not isinstance(piece, dict):
                raise ValueError("expected an object")
        except (ValueError, UnicodeError) as error:
            raise EngineError(f"Ollama returned invalid JSON: {error}") from None
        if piece.get("error"):
            raise EngineError(str(piece["error"]))
        return piece

    def stream(self, messages: list[dict[str, str]], max_new_tokens: int, max_time: float,
               stop: threading.Event) -> Iterator[tuple[str, Any]]:
        """Close only this chunk's response on exit; never mutate caller's stop event."""
        if stop.is_set():
            return
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        # Reserve room for this exact prompt plus its output; do not truncate an oversized sentence.
        context = max(4096, self.count(prompt) + max_new_tokens)
        body = {"model": self.model, "prompt": prompt, "raw": True, "stream": True,
                "options": {**self._options(), "num_ctx": context, "num_predict": max_new_tokens}}
        deadline = time.monotonic() + max_time
        try:
            with _call(self.url, "/api/generate", body, max_time) as response:
                for raw in response:
                    if stop.is_set():
                        return
                    if time.monotonic() >= deadline:
                        raise EngineError("Ollama generation timed out")
                    piece = self._decode(raw)
                    if text := piece.get("response"):
                        yield "content", text
                    if piece.get("done"):
                        yield "done", {"prompt_tokens": piece.get("prompt_eval_count", 0),
                                       "completion_tokens": piece.get("eval_count", 0),
                                       "finish": "length" if piece.get("done_reason") == "length" else "stop"}
                        return
                if not stop.is_set():
                    raise EngineError("Ollama stream ended before done")
        except (OSError, http.client.HTTPException) as error:
            raise EngineError(f"Ollama stream failed: {error}") from None


def engine_from_env(*, config: Any = None, **options: Any) -> S1MiniEngine | None:
    """URL opt-in like LFM3; saved startup settings win over environment values."""
    def value(name: str, default: str) -> str:
        return str(config.get(name) if config else os.environ.get(f"SERVICE_{name.upper()}", default)).strip()

    url = value("ollama_url", "").rstrip("/")
    if not url:
        return None
    model = value("ollama_model", DEFAULT_OLLAMA_MODEL) or DEFAULT_OLLAMA_MODEL
    tokenizer_source = value("model", DEFAULT_MODEL)

    def local_digest(_: str) -> str | None:
        name = model if ":" in model.rsplit("/", 1)[-1] else f"{model}:latest"
        with _call(url, "/api/tags", None, 15) as response:
            reply = _read_json(response)
        return next((row["digest"] for row in reply.get("models", []) if row["name"] == name), None)

    def pull(_: str) -> None:
        raise EngineError("S1-mini is a pinned local GGUF import: re-import with ollama create, then restart the service")

    engine = S1MiniEngine(
        model, loader=lambda source: OllamaLoaded(url, source, load_tokenizer(tokenizer_source),
                                                 threads=lambda: engine.num_thread),
        set_threads=lambda count: None, cached_sha=local_digest,
        remote_sha=lambda source: local_digest(source) or "", download=pull, **options)
    engine.backend = "ollama"
    return engine
