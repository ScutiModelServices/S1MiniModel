# S1MiniModel: without Docker, on Windows

Run S1-mini on the CPU directly with Python: one process, no load balancer, listening on `127.0.0.1:9220`.

## Requirements
- Windows with Python 3.11 or newer and uv (`winget install astral-sh.uv`).
- Internet on the first start (about 1.5 GB of weights).
- RAM for the model (one copy).

## Start
Double-click `run.bat`, or run it in a terminal from `S1MiniModel\`. Choose **1 Run the service** in the menu, or run `run.bat run` to skip the menu. It runs `uv sync` to create or update `.venv`, then starts
`python src/app.py`. The first start downloads about 1.5 GB of weights.

Linux or macOS:
```bash
cd S1MiniModel
uv sync
uv run python src/app.py
```

## Settings
`run.bat` loads `.env` in this folder (copy `.env.example`); a real environment variable wins over it. Set variables in `.env` or in the environment before starting:

| Variable | Default | Effect |
|---|---|---|
| `S1MINI_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` only if other devices must reach it. |
| `S1MINI_PORT` | `9220` | Port. |
| `S1MINI_ADMIN_PASSWORD` | empty | Unlocks `/admin/` and requires tokens on every call but `/health`. Empty = no auth. |
| `S1MINI_WARM` | `1` | Load the model at start; with `0` the first request pays the load time. |
| `S1MINI_NUM_THREAD` | the library decides | CPU threads. Set it to the number of **physical** cores. |

PowerShell: `$env:S1MINI_ADMIN_PASSWORD = "secret"; .\run.bat`
Bash: `S1MINI_ADMIN_PASSWORD=secret uv run python src/app.py`

## Check
```bash
curl http://127.0.0.1:9220/health
```
`ready` is `false` until the model has loaded. Then open `http://127.0.0.1:9220/admin/` (see [guide-web-ui.md](guide-web-ui.md)),
make a token, and try a call:
```bash
curl -X POST http://127.0.0.1:9220/v1/normalize -H "Content-Type: application/json" -H "X-Internal-Token: s1mini_..." -d '{"text":"so um i need to like send the report by uh friday no wait thursday"}'
```

## Stop
Ctrl+C in the terminal. Do not run this and the Docker stack together: both use port 9220.

## Tests
`uv run pytest`.
