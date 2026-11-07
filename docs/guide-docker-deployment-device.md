# S1MiniModel: Docker on a deployment machine

Run S1-mini on the CPU on a separate always-on machine (default `lex@scutiserver1.local`, folder
`/media/ZimaOS-HD/Apps/S1MiniModel`). Callers reach it over the published port.

## Requirements on the machine

- Docker + Compose v2, and ssh access (root over ssh is refused; use the normal user).
- Enough RAM for the model times `S1MINI_REPLICAS`.

## 1. Publish the code (from your PC)

Run `S1MiniModel\run.bat` and choose **Deploy** (or `run.bat deploy`). Menu:

| Option | Does |
|---|---|
| 1 | Publish code to the `live` branch |
| 2 | Copy your `.env` to the server (one ssh/tar session, one password prompt) |
| 3 | Both |
| 4, 5 | Dry runs of 1 and 2 |
| 6 | chown helper, if option 2 says `Permission denied` |
| R | Release: publish, then tag `VERSION` |

Keep your own target in the git-ignored `tools\deploy.local.ini` (copy `tools\deploy.local.example.ini`), or set
`DEPLOY_HOST`, `DEPLOY_DIR` and `DEPLOY_WEB_PORT` before running. Commit `main` first: publish reads committed `main`.

## 2. First-time setup on the machine

```bash
mkdir -p /media/ZimaOS-HD/Apps
git clone -b live <your-repo-url> /media/ZimaOS-HD/Apps/S1MiniModel
cd /media/ZimaOS-HD/Apps/S1MiniModel
```
Create `.env` (deploy option 2 copies yours, or `cp .env.example .env` and edit):
- `S1MINI_ADMIN_PASSWORD`: a real password.
- `S1MINI_REPLICAS=1` unless you have the memory for more.
- `S1MINI_PORT=9220` (published on all interfaces; firewall it if the LAN should not reach it, or bind it to
  `127.0.0.1` in the `ports:` line of `s1mini_lb` when only callers on the machine need it).

## 3. Start

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:9220/health
```
The first start downloads about 1.5 GB of weights into the `models` volume; `s1mini_lb` waits for a healthy service
(up to 300 s grace).

## 4. Connect callers

1. Open `http://<machine-ip>:9220/admin/`, sign in with the admin password and create one token per caller
   (see [guide-web-ui.md](guide-web-ui.md)).
2. The caller holds the URL and token:
   - Caller on another machine: `http://<machine-ip>:9220`.
   - Caller in a Docker stack on the same machine: `http://host.docker.internal:9220`.
3. Try a call from the machine:
   ```bash
   curl -X POST http://127.0.0.1:9220/v1/normalize -H "Content-Type: application/json" -H "X-Internal-Token: s1mini_..." -d '{"text":"so um i need to like send the report by uh friday no wait thursday"}'
   ```

## Scaling

```bash
S1MINI_REPLICAS=3 docker compose up -d --build
docker compose restart s1mini_lb
```

The restart is needed because nginx resolves replica addresses once at start.

## Updating

```bash
cd /media/ZimaOS-HD/Apps/S1MiniModel
git pull
docker compose up -d --build
docker compose restart s1mini_lb
```

## Releasing

A plain publish (`run.bat`, Deploy, option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `run.bat`, Deploy, option R or
`py tools\publish_live.py --release`. `run.bat`, Build the release ZIP, then builds `_zip_versions\S1MiniModel-<VERSION>.zip`.

## Problems

| Symptom | Fix |
|---|---|
| Caller cannot reach the service | Check the caller's URL and token, and that `curl http://<machine-ip>:9220/health` works. |
| nginx 502 after an update | `docker compose restart s1mini_lb`. |
| Permission denied on push | run.bat Deploy option 6. |
| Port 9220 in use | Another stack on the machine already publishes it. |
