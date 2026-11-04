# S1MiniModel

Superwhisper S1-mini (0.6B speech-to-text normalizer, Qwen3) served over HTTP, behind the shared model-service admin page, tokens and settings. Port 9220, env prefix `S1MINI_`, token prefix `s1mini_`.

## Agent instructions
This file is the one instruction file for every coding agent; `CLAUDE.md` only imports it (`@AGENTS.md`). Edit this file, never `CLAUDE.md`.

## Rules
- Follow the `model-service-parity` skill and `AI/ModelServices/SHARED-FEATURES.md` (what must match in every model service) and `AI/ModelServices/SERVICE-SPECIFIC.md` (what differs on purpose). A change to a shared feature goes to every service; a new difference goes into `SERVICE-SPECIFIC.md` in the same change.
- `web/index.html`, `src/tokens.py`, `src/settings.py`, `src/updates.py` and `.dockerignore` are copies shared with the other model services. Change one, copy it to the others, run `python tools/check_sync.py` in each repo.
- Built from LFM3Model (same engine shape and shared files). Differences: `POST /v1/normalize` instead of `/v1/chat`; the required system prompt and control line are fixed in `src/engine.py` (word for word from the model card; do not reword); decoding is always greedy; thinking is off through the chat template (`enable_thinking=False`); no `trust_remote_code`, no project models, no `temperature`/`max_tokens`; long input is chunked at sentence ends (`src/sentences.py`); streaming is one JSON line per sentence, not per token.
- `Loaded.stream` has its own `halt` event; the caller's `stop` spans all chunks of a call, so never set it when one chunk ends.
- Behaviour changes update `README.md`, `deployment.md`, `docs/guide-web-ui.md`, `.env.example` and `CHANGELOG.md` in the same commit.
- Tests: `uv run pytest -q`. `tests/test_admin_ui.py` needs Playwright and its browser and is skipped without it. On Windows, if uv fails with "cannot move the file to a different disk drive", set `UV_CACHE_DIR` to a folder on the same drive and `UV_LINK_MODE=copy`.
- Never read or print `.env`, `tokens.json` or `settings.json`.
- Commit with the noreply author email `214214011+scutiii2@users.noreply.github.com` (another address is rejected on push). Push `main`, then run `python tools/publish_live.py`. Build Docker only when the Dockerfile or the dependencies changed.
