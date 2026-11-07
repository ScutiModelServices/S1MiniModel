# S1MiniModel: Docker Desktop on this PC

Run S1-mini on the CPU in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements

- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- About 2 GB of RAM **per replica** (each replica holds the model). Keep `S1MINI_REPLICAS=1` on a PC. Docker Desktop on Windows caps its engine at about half of your RAM unless you raise it in `.wslconfig`.
- Network access on the first start to download the weights (about 1.5 GB) from Hugging Face.
- CPU only. The Dockerfile installs the CPU build of torch and fails the build if a CUDA or ROCm build is found.

## Steps

1. Configure. In `S1MiniModel/`:
   ```bash
   cp .env.example .env
   ```
   Set `S1MINI_ADMIN_PASSWORD` (empty = no auth and no admin page, fine for a local test). Leave `S1MINI_PORT=9220`. Leave `S1MINI_REPLICAS=1`.
2. Start:
   ```bash
   docker compose up -d --build
   ```
   The first start downloads about 1.5 GB of weights into the `models` volume. `s1mini_lb` starts only after the service is healthy
   (up to 300 s grace). Watch with `docker compose ps` and `docker compose logs -f s1mini`.
3. Check:
   ```bash
   curl http://127.0.0.1:9220/health
   ```
   `ready` is `false` until the model has loaded, then `true`.
4. Open the admin page: `http://127.0.0.1:9220/admin/` (see [guide-web-ui.md](guide-web-ui.md)) and make a token for each caller.
5. Try a call:
   ```bash
   curl -X POST http://127.0.0.1:9220/v1/normalize -H "Content-Type: application/json" -H "X-Internal-Token: s1mini_..." -d '{"text":"so um i need to like send the report by uh friday no wait thursday"}'
   ```
   Expect a JSON answer.
6. Callers connect to the published port. The caller holds the URL and token:
   - Caller on the host: `http://127.0.0.1:9220`.
   - Caller in another Docker stack on the same host: `http://host.docker.internal:9220`.

## Settings

In `.env` next to `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `S1MINI_REPLICAS` | `1` | Number of `s1mini` containers. Read by Compose. |
| `S1MINI_MEM_LIMIT` | `0` (no cap) | RAM cap per container, for example `3g` (bfloat16 weights use about 1.4 GiB). An out-of-memory kill then stays in the container instead of starving the host. Read by Compose. |
| `S1MINI_PORT` | `9220` | Host port `s1mini_lb` publishes. |
| `S1MINI_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a token as `X-Internal-Token`. Empty = no auth. |
| `S1MINI_NUM_THREAD` | torch decides | Starting value for the CPU threads card; a value saved on `/admin/` wins. Use the number of physical cores (`lscpu`: cores x sockets), not logical CPUs; more threads than cores slows every call. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`S1MINI_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`S1MINI_MAX_INFLIGHT`, 0 = 4), answers kept per replica (`S1MINI_CACHE_SIZE`, 256, 0 = off), input tokens per pass (`S1MINI_CHUNK_TOKENS`, 800), base model
(`S1MINI_MODEL`, restart), number format (`S1MINI_DTYPE`, restart: `bfloat16` or `float32`; try `float32` if answers take many seconds on a CPU without native bfloat16 maths, it needs twice the RAM) and load at start (`S1MINI_WARM`, restart). Compose does not pass these; add the variable
under `environment:` of `s1mini` to use one as a starting value.

## Daily use

```bash
docker compose ps          # state
docker compose logs -f s1mini
docker compose down        # stop (the weights volume is kept)
docker compose up -d --build && docker compose restart s1mini_lb   # after a code change
```

## Problems

| Symptom | Fix |
|---|---|
| `address already in use` on 9220 | Another copy (`run.bat`, or the same stack on another compose project) is running. Stop it or change `S1MINI_PORT`. |
| `/health` shows `ready: false` for minutes | First start: the weights are downloading or loading. Check `docker compose logs -f s1mini`. |
| 401 Invalid token | The caller's token is missing or revoked; make one on `/admin/`. |
| Container restarts in a loop | Out of RAM. Raise the Docker Desktop memory limit or lower the replica count. |
| `s1mini_lb` never starts | No replica is healthy yet (first download, or out of memory). `docker compose logs s1mini`. |
| Replicas restart in a loop | Out of RAM. Lower `S1MINI_REPLICAS`. |
| 422 on `/v1/normalize` | A field is wrong: `styling`, `structure` and `context` accept only the listed values, and no other field is allowed. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| Slow answers | CPU speed with `transformers` is modest for any model of this size; use a 4-bit GGUF runtime if speed matters. Raise CPU threads on `/admin/`. |
| nginx 502 after scaling | `s1mini_lb` not restarted after the replica count changed. |
