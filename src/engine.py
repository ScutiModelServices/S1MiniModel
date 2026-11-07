"""S1-mini (a 0.6B Qwen3 text normalizer for speech-to-text output) run in this process on the CPU with `transformers`.

The model is not a chat model: every call sends the fixed system prompt and one control line, then the transcript,
and decodes greedily with thinking switched off in the chat template (without that the model emits an empty
<think> block and stops). Long transcripts are cut at sentence ends into chunks of at most `chunk_tokens` tokens,
each normalized on its own. Output is handed out sentence by sentence, not token by token.

One generation runs at a time per replica (torch already uses every core); scale with replicas.

shortcut: a single sentence longer than `chunk_tokens` is sent whole; an empty result (filler-only input) is valid."""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator

from sentences import SentenceBuffer, chunks

DEFAULT_MODEL = "superwhisper/s1-mini"

# Required by the model card, word for word; any change makes the model hallucinate.
SYSTEM_PROMPT = (
    "You are a text normalizer for speech-to-text transcripts. The input begins "
    "with a control line specifying the styling, structure, and context settings; "
    "clean the transcript to match those settings and output only the cleaned text."
)
STYLINGS = ("casual", "semi-casual", "semi-formal", "formal")
STRUCTURES = ("prose", "lists")
CONTEXTS = ("general", "email")


class EngineError(RuntimeError):
    """The model could not answer. `status` is the HTTP status the service maps it to."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def messages_for(text: str, styling: str, structure: str, context: str) -> list[dict[str, str]]:
    control = f"[Styling: {styling}] [Structure: {structure}] [Context: {context}]"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"{control}\n{text}"}]


class Loaded:
    """A tokenizer and model that normalize one chunk of text."""

    def __init__(self, tokenizer: Any, model: Any) -> None:
        self.tokenizer, self.model = tokenizer, model

    def count(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    def stream(self, messages: list[dict[str, str]], max_new_tokens: int, max_time: float,
               stop: threading.Event) -> Iterator[tuple[str, Any]]:
        """("content", text) pieces as the model makes them, then ("done", stats). Setting `stop` ends the generation
        after the token being made."""
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        ids = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                                 return_dict=True, enable_thinking=False)
        prompt = ids["input_ids"].shape[1]
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        result: dict[str, Any] = {}
        halt = threading.Event()  # ours: ends this chunk only; `stop` is the caller's and spans all chunks

        class Stopped(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return torch.full((input_ids.shape[0],), stop.is_set() or halt.is_set(), dtype=torch.bool, device=input_ids.device)

        def run() -> None:
            try:
                with torch.inference_mode():
                    result["out"] = self.model.generate(**ids, max_new_tokens=max_new_tokens, max_time=max_time, do_sample=False,
                                                        streamer=streamer, stopping_criteria=StoppingCriteriaList([Stopped()]))
            except BaseException as error:  # the streamer would wait for the end of a generation that crashed
                result["error"] = error
                streamer.on_finalized_text("", stream_end=True)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            for text in streamer:
                if text:  # the streamer also hands out empty pieces (skipped special tokens)
                    yield "content", text
            worker.join()
            if "error" in result:
                raise result["error"]
            new = result["out"][0][prompt:]
            yield "done", {"prompt_tokens": prompt, "completion_tokens": len(new),
                           "finish": "length" if len(new) >= max_new_tokens else "stop"}
        finally:
            halt.set()
            worker.join()


DTYPES = ("bfloat16", "float32")


def load(source: str, dtype: str = "bfloat16") -> Loaded:
    """`source`: a Hub repository or a checkpoint folder. `float32` is faster on CPUs without native bfloat16 maths
    and needs twice the memory."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(source, dtype=getattr(torch, dtype))
    model.eval()
    return Loaded(AutoTokenizer.from_pretrained(source), model)


def _set_threads(count: int) -> None:
    import torch

    torch.set_num_threads(count)


def _remote_sha(repo: str) -> str:
    from huggingface_hub import HfApi

    return HfApi().model_info(repo, token=False).sha


def _cached_sha(repo: str) -> str | None:
    from huggingface_hub import snapshot_download

    try:
        return Path(snapshot_download(repo_id=repo, local_files_only=True, token=False)).name  # the folder is named by commit
    except OSError:
        return None


def _download(repo: str) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=repo, token=False)


def default_marker() -> Path:
    """File in the shared models volume whose content changes when one replica downloads new weights."""
    configured = os.environ.get("SERVICE_WEIGHTS_MARKER")
    return Path(configured) if configured else Path(os.environ.get("HF_HOME") or "~/.cache/huggingface").expanduser() / ".s1mini-weights-version"


class S1MiniEngine:
    """The `loader`, `set_threads`, `remote_sha`, `cached_sha` and `download` callables are injectable for tests."""

    def __init__(self, model: str = DEFAULT_MODEL, *, chunk_tokens: int = 800, timeout: float = 120.0,
                 marker: Path | None = None, loader: Callable[[str], Loaded] | None = None, dtype: str = "bfloat16",
                 set_threads: Callable[[int], None] = _set_threads,
                 remote_sha: Callable[[str], str] = _remote_sha, cached_sha: Callable[[str], str | None] = _cached_sha,
                 download: Callable[[str], None] = _download) -> None:
        self.model = model
        self.chunk_tokens = chunk_tokens
        self._threads: int | None = None
        self._timeout = timeout
        self._marker = marker
        self._seen = self._read_marker()
        if dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {', '.join(DTYPES)}, not {dtype!r}")
        self.dtype = dtype
        self._loader = loader or (lambda source: load(source, self.dtype))
        self._set_threads = set_threads
        self._remote_sha_of, self._cached_sha_of, self._download_of = remote_sha, cached_sha, download
        self._base: Loaded | None = None
        self._load_lock = threading.Lock()
        self._gate = asyncio.Semaphore(1)
        self.generation = 0  # part of the answer cache key; changes whenever the loaded model is dropped

    @property
    def num_thread(self) -> int | None:
        return self._threads

    @num_thread.setter
    def num_thread(self, count: int) -> None:
        if count != self._threads:
            self._set_threads(count)
            self._threads = count

    @property
    def ready(self) -> bool:
        return self._base is not None

    async def close(self) -> None:
        self._base = None

    async def warm(self) -> None:
        """Load the model now so the first request does not pay for it."""
        await asyncio.to_thread(self._base_model)

    def _base_model(self) -> Loaded:
        with self._load_lock:
            if self._base is None:
                self._base = self._loader(self.model)
            return self._base

    def _events(self, text: str, styling: str, structure: str, context: str, stop: threading.Event) -> Iterator[tuple[str, Any]]:
        """("sentence", text with the whitespace after it) as sentences complete, then ("done", stats)."""
        loaded = self._base_model()
        parts = chunks(text, loaded.count, self.chunk_tokens)
        gap = "\n" if structure == "lists" else " "
        prompt = completion = 0
        finish = "stop"
        for number, part in enumerate(parts):
            window = int(1.3 * loaded.count(part) + 32)  # output length tracks input length (model card)
            buffer = SentenceBuffer()
            for kind, value in loaded.stream(messages_for(part.strip(), styling, structure, context), window, self._timeout, stop):
                if kind == "content":
                    for sentence in buffer.feed(value):
                        yield "sentence", sentence
                else:
                    prompt += value["prompt_tokens"]
                    completion += value["completion_tokens"]
                    if value["finish"] == "length":
                        finish = "length"
            tail = buffer.flush()
            if tail.strip():  # the last sentence has no whitespace after it yet
                yield "sentence", tail + (gap if number < len(parts) - 1 else "")
        yield "done", {"prompt_tokens": prompt, "completion_tokens": completion, "finish": finish}

    async def normalize(self, text: str, styling: str, structure: str, context: str) -> dict[str, Any]:
        stop = threading.Event()
        async with self._gate:
            def run() -> dict[str, Any]:
                events = list(self._events(text, styling, structure, context, stop))
                return {**events[-1][1], "content": "".join(v for k, v in events if k == "sentence").strip()}

            return await asyncio.to_thread(run)

    async def normalize_stream(self, text: str, styling: str, structure: str, context: str) -> AsyncIterator[tuple[str, Any]]:
        """("sentence", text) pieces, then ("done", stats). Holds the generation slot until the last piece; when the
        caller closes the iterator the generation is stopped."""
        stop = threading.Event()
        async with self._gate:
            events = self._events(text, styling, structure, context, stop)
            try:
                while (event := await asyncio.to_thread(next, events, None)) is not None:
                    yield event
            finally:
                stop.set()  # a running `next` then ends by itself; closing the generator here could race with it

    # Updates: the Hub revision of the weights, shared by all replicas through one models volume.

    async def cached_sha(self) -> str | None:
        return await asyncio.to_thread(self._cached_sha_of, self.model)

    async def remote_sha(self) -> str:
        return await asyncio.to_thread(self._remote_sha_of, self.model)

    async def pull(self) -> None:
        await asyncio.to_thread(self._download_of, self.model)

    async def unload(self) -> None:
        """Forget the loaded model here and tell the other replicas to do the same; the next call loads the new weights."""
        if self._marker is not None:
            self._marker.parent.mkdir(parents=True, exist_ok=True)
            self._seen = uuid.uuid4().hex
            self._marker.write_text(self._seen, "utf-8")
        self._forget()

    def sync(self) -> None:
        """Called every few seconds: drop the loaded model when another replica downloaded new weights."""
        current = self._read_marker()
        if current != self._seen:
            self._seen = current
            self._forget()

    def _forget(self) -> None:
        with self._load_lock:
            self._base = None
            self.generation += 1  # kept answers are from the old weights

    def _read_marker(self) -> str | None:
        try:
            return self._marker.read_text("utf-8") if self._marker else None
        except OSError:
            return None
