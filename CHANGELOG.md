# Changelog

## Unreleased

- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.

- `run.bat`: runs `uv sync` directly; `python -m uv` failed when uv was installed only as a program (winget).
- First version: Superwhisper S1-mini (0.6B speech-to-text normalizer) served on the CPU with `transformers`, with the
  admin page, tokens (rate limit, expiry), metrics, Settings card, update checks, weight downloads and answer cache
  shared with the other model services.
- `POST /v1/normalize` takes `text`, `styling`, `structure`, `context` and `stream`. `stream: true` sends one JSON line
  per sentence, then `done`.
- Long input is cut at sentence ends into passes of `S1MINI_CHUNK_TOKENS` tokens (default 800).
