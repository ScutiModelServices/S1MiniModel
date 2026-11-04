# S1MiniModel

The one place S1-mini is served. S1-mini is a 0.6B text normalizer for speech-to-text output (Qwen3 fine-tune by
Superwhisper). Projects send it a raw transcript over HTTP and get clean text back: fillers removed, self-corrections
resolved, punctuation and capitals added, spoken numbers, times and emails written out. It is not a chat model.
English only. It has the same admin page, tokens, rate limits, metrics, settings and update checks as the other
model services.

The model runs in this process on the CPU with `transformers` (about 1.5 GB of weights, bfloat16). The service
always sends the system prompt the model card requires, word for word, and decodes greedily with thinking off.

## API

| Call | Purpose |
|---|---|
| `POST /v1/normalize` | `{"text", "styling", "structure", "context", "stream"}` → `{"content", "finish_reason", "model", "usage", "duration_ms"}`. |
| `GET /health` | `{"status": "ok", "model", "ready", "num_thread"}`; `ready` is true once the model is loaded. No token needed. |

`styling`: `casual`, `semi-casual`, `semi-formal` (default), `formal`. `structure`: `prose` (default) or `lists`.
`context`: `general` (default) or `email`. Other values are refused with 422: the model garbles output for values it
was not trained on. Any other field (`messages`, `tools`, `temperature`, ...) is refused with 422 too.

Example: `so um i need to like send the the report by uh friday no wait make that thursday` becomes
`So I need to send the report by Thursday.`

An empty `content` is a valid result (a transcript that holds only fillers).

**Long text.** Input is cut at sentence ends into passes of at most *Input tokens per pass* (`S1MINI_CHUNK_TOKENS`,
default 800; the model card advises under about 1000) and each pass is normalized on its own. One sentence longer than
the limit is sent whole. Output joins with a space (a newline for `lists`).

**Streaming, per sentence.** With `"stream": true` the reply is `application/x-ndjson`. One line per finished
sentence, not per token: `{"type": "sentence", "text": "So I need to send the report by Thursday. "}`, then
`{"type": "done", ...}` holding the same body a call without `stream` returns. Each `text` keeps the whitespace that
follows it, so joining the pieces gives the answer. The first sentence arrives when the model has finished it. A
refusal before the first sentence (a full queue) is a normal HTTP error; a failure after it is sent as
`{"type": "error", "status", ...}` and ends the stream. A kept answer (see below) is streamed back sentence by sentence.

**Cache.** *Answers kept per replica* (`S1MINI_CACHE_SIZE`, default 256, 0 = off) keeps the last answers for identical
requests and sends them again without generating (`X-Cache: hit`). Decoding is always greedy, so every request is
kept. New weights empty the cache. The cache is per replica, so with N replicas the hit rate is about 1/N. `stream`
does not change the key.

**Tokens.** A token's "allowed projects" list has no effect here: there is one model and no project models.

## Admin page

`/admin/` (password `S1MINI_ADMIN_PASSWORD`): tokens with rate limit and expiry, usage numbers, CPU threads, the
Settings card (update check hours, in-flight cap, answers kept, input tokens per pass), and the Updates card
(**Check now** and **Download new weights** for the Hugging Face repository). New weights are downloaded once into
the shared models volume; the other replicas notice within a few seconds and load them on their next request.
`/metrics` (admin password) is Prometheus text per token. `s1mini_request_seconds` is a histogram of how long each
`/v1` call took on the replica that answers (to the first byte for a streamed reply); it starts from 0 when the
replica restarts.

## Run

```bash
docker compose up -d --build        # http://<host>:9220
```

Without Docker: `run.bat` (uv, listens on `127.0.0.1:9220`). The first start downloads about 1.5 GB. Each replica
holds the model in RAM (about 2 GB), so `S1MINI_REPLICAS` multiplies memory use. See `deployment.md`.

## Tests

```bash
uv sync
uv run pytest
```

## Limits worth knowing

- One generation at a time per replica; extra calls wait, and more than the in-flight cap get 429.
- The rate limit is per replica.
- A pass stops after 120 s and returns what it has with `finish_reason: "length"`.
- A style that drops end punctuation (`casual`) can leave no full stop between two passes of a long text.
- Licence: Apache 2.0 plus a naming clause. Wherever the model is named it must be "S1-mini" by "Superwhisper". Read
  the `LICENSE` on the Hub before redistributing.


## Try it from the admin page

Open `/admin/` and use **Try it** to call the public API with a service token held only in memory. Runs use normal token scopes, limits and caches; the panel shows HTTP status, latency, responses, cancellation and a curl equivalent with a token placeholder. See [the web UI guide](docs/guide-web-ui.md#try-it-send-a-real-request).

Normalize sends transcript text plus styling, structure and context to `POST /v1/normalize`. Streaming appends sentence events as they arrive. This cleans text with S1-mini by Superwhisper; it does not transcribe uploaded audio or act as a general chat model.
