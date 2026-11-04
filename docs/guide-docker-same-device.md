# S1MiniModel: Docker Desktop on this PC

Run S1-mini on the CPU in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements
- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- RAM for the model **per replica**. Keep `S1MINI_REPLICAS=1` on a PC. Docker Desktop on Windows caps its engine at about half of your RAM unless you raise it in `.wslconfig`.
- Internet on the first start (about 1.5 GB of weights).

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
