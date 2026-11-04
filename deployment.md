# Deploying S1MiniModel

S1MiniModel is one HTTP service (port 9220). It runs as `s1mini` replicas behind an nginx load balancer,
`s1mini_lb`. Callers use `http://<host>:9220`; they never reach a replica directly.

## Requirements

- Docker with Compose v2.
- About 2 GB of RAM **per replica** (each replica holds the model).
- Network access on the first start to download the weights (about 1.5 GB) from Hugging Face.
- CPU only. The Dockerfile installs the CPU build of torch and fails the build if a CUDA or ROCm build is found.

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

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:9220/health
```

Expect `"ready": true` once a replica has loaded the model. The first start downloads the weights into the `models`
volume, so `s1mini_lb` can take a few minutes to appear (the health check allows 300 s before failures count; run
`docker compose ps` and wait).

## Scaling

```bash
S1MINI_REPLICAS=3 docker compose up -d --build
docker compose restart s1mini_lb
```

The restart is needed because nginx resolves replica addresses once at start.

## Updating the weights

The **Updates** card compares the downloaded revision of the Hugging Face repository with its newest one. **Download
new weights** fetches it into the models volume; every replica drops its old copy within a few seconds and loads the
new one on its next request (it needs RAM for both for a moment). The download is the repository's current `main`.
Updating the service itself: `docker compose up -d --build`, then `docker compose restart s1mini_lb`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `s1mini_lb` never starts | No replica is healthy yet (first download, or out of memory). `docker compose logs s1mini`. |
| Replicas restart in a loop | Out of RAM. Lower `S1MINI_REPLICAS`. |
| 401 "Invalid token" | The caller sends no token, or a revoked one. |
| 422 on `/v1/normalize` | A field is wrong: `styling`, `structure` and `context` accept only the listed values, and no other field is allowed. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| Slow answers | CPU speed with `transformers` is modest for any model of this size; use a 4-bit GGUF runtime if speed matters. Raise CPU threads on `/admin/`. |
| nginx 502 after scaling | `s1mini_lb` not restarted after the replica count changed. |

## Releasing

A plain publish (`tools\deploy.bat` option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `tools\deploy.bat` option R or
`py tools\publish_live.py --release`. `tools\make_zip.bat` then builds `zip_versions\S1MiniModel-<VERSION>.zip`.
