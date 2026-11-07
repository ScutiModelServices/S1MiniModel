# Changelog

## Unreleased

- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Optional host Ollama backend (`S1MINI_OLLAMA_URL`, `S1MINI_OLLAMA_MODEL`) with torch fallback.
  Imports official pinned S1-mini by Superwhisper F16 GGUF using `Modelfile`; no conversion needed.
  Keeps exact HF-rendered non-thinking prompt, greedy decoding, token-based sentence chunking,
  sentence streaming, cache and 422 rules. CPU threads apply to each Ollama chunk. Transport errors
  map to EngineError; chunk completion never sets the caller's stop event. Updates report local
  digests and require explicit re-import. Adds fake-server tests and repeatable CPU/quality comparison.
  Ryzen 7 7445HS, six CPU threads: torch bf16 9.169 vs Ollama F16 17.097 output tok/s (1.86×);
  all twelve synthetic outputs identical. See `docs/backend-comparison.md` for method and limits.

- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.

- `run.bat`: runs `uv sync` directly; `python -m uv` failed when uv was installed only as a program (winget).
- First version: Superwhisper S1-mini (0.6B speech-to-text normalizer) served on the CPU with `transformers`, with the
  admin page, tokens (rate limit, expiry), metrics, Settings card, update checks, weight downloads and answer cache
  shared with the other model services.
- `POST /v1/normalize` takes `text`, `styling`, `structure`, `context` and `stream`. `stream: true` sends one JSON line
  per sentence, then `done`.
- Long input is cut at sentence ends into passes of `S1MINI_CHUNK_TOKENS` tokens (default 800).
