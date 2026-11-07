# Changelog

## Unreleased

### Breaking: common service environment variables

Service-owned environment variables now use `SERVICE_*`. Old names are no longer read.
Rename old names once in your real `.env`, Compose `environment:` block, and CI/secret settings.

| Old name | New name |
|---|---|
| `S1MINI_ADMIN_PASSWORD` | `SERVICE_ADMIN_PASSWORD` |
| `S1MINI_CACHE_SIZE` | `SERVICE_CACHE_SIZE` |
| `S1MINI_CHUNK_TOKENS` | `SERVICE_CHUNK_TOKENS` |
| `S1MINI_DTYPE` | `SERVICE_DTYPE` |
| `S1MINI_HOST` | `SERVICE_HOST` |
| `S1MINI_MAX_INFLIGHT` | `SERVICE_MAX_INFLIGHT` |
| `S1MINI_MEM_LIMIT` | `SERVICE_MEM_LIMIT` |
| `S1MINI_MODEL` | `SERVICE_MODEL` |
| `S1MINI_NUM_THREAD` | `SERVICE_NUM_THREAD` |
| `S1MINI_OLLAMA_MODEL` | `SERVICE_OLLAMA_MODEL` |
| `S1MINI_OLLAMA_URL` | `SERVICE_OLLAMA_URL` |
| `S1MINI_PORT` | `SERVICE_PORT` |
| `S1MINI_REPLICAS` | `SERVICE_REPLICAS` |
| `S1MINI_TOKENS_FILE` | `SERVICE_TOKENS_FILE` |
| `S1MINI_UPDATE_CHECK_HOURS` | `SERVICE_UPDATE_CHECK_HOURS` |
| `S1MINI_WARM` | `SERVICE_WARM` |
| `S1MINI_WEB_DIR` | `SERVICE_WEB_DIR` |
| `S1MINI_WEIGHTS_MARKER` | `SERVICE_WEIGHTS_MARKER` |

- Move the default service port from 9220 to 29280, including API replicas and the nginx load balancer. Update any explicit old port in your real `.env`, saved tool-service `backends.json` connections, and browser or MCP client configuration once. With Compose defaults, recreate the stack to use the new host and container ports; a custom host-port override stays as configured, while container ports still change to 29280.

- Renamed `S1MiniModel` to `STC_S1Mini_Model`; Docker project, API image, services, load balancer and volumes now use `stc_s1mini_model` names. Callers on `citadel_core` connect to `stc_s1mini_model_lb` at the existing port.
- Docker volume migration: existing volumes with old names are orphaned; renaming does not move data. Stop the old stack before copying; never use `down -v`. The commands below assume the previous default Compose project name; substitute actual volume names if `-p` or `COMPOSE_PROJECT_NAME` overrode it.
  - `s1mini_models` → `stc_s1mini_model_models`: `docker volume inspect s1mini_models && docker volume create stc_s1mini_model_models && docker run --rm -v s1mini_models:/from:ro -v stc_s1mini_model_models:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
  - `s1mini_tokens` → `stc_s1mini_model_data`: `docker volume inspect s1mini_tokens && docker volume create stc_s1mini_model_data && docker run --rm -v s1mini_tokens:/from:ro -v stc_s1mini_model_data:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
- To retain an old volume instead, set its top-level volume definition to `external: true` and `name: <old-volume-name>` in a local Compose override. Rollback: stop the renamed stack, restore the previous checkout and folder name, and restart the old stack with its original volumes; copy back newer data first if the renamed stack accepted writes.

- `run.bat` loads `.env` from the service folder for a local run: it passes `--dotenv`, the service prints which variable names it loaded (never the values), and a real environment variable still wins. A plain `python src/app.py` and Docker never read `.env`.
- Untracked folders now start with `.` or `_`: `zip_versions/` is `_zip_versions/`. A local `voices`, `tem_code` or `zip_versions` folder from an older checkout needs renaming by hand.
- `run.bat` is now a menu (run the service, deploy, build the release ZIP) and `run.bat run|deploy|zip` skips it. `tools/deploy.bat`, `tools/make_zip.bat` and `tools/deploy.local.example.bat` are gone; the local deploy target is `tools/deploy.local.ini` (copy `tools/deploy.local.example.ini`).
- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Optional host Ollama backend (`SERVICE_OLLAMA_URL`, `SERVICE_OLLAMA_MODEL`) with torch fallback.
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
- Long input is cut at sentence ends into passes of `SERVICE_CHUNK_TOKENS` tokens (default 800).
