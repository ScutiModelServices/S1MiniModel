# Host Ollama setup and verification

S1-mini by Superwhisper has [official GGUF exports](https://huggingface.co/superwhisper/s1-mini-GGUF).
No HF-to-GGUF conversion is needed. This service uses the official **F16** export first to
avoid introducing Q4 quantization loss. Q4_K_M is available upstream but requires its own
quality comparison before use. A public GGUF is not evidence of output parity.

## Reproducible import (PowerShell, from this repository)

The original repository did **not** pin its HF model revision: `src/engine.py` used
`from_pretrained(source)` and followed `main`. The cached HF revision used for this change's
baseline is `88f6b15896c73bbb13a3b596e0afe8ea0d5150b4`. The official GGUF repository is pinned
here to `34add00a48a2e5d24e5a4ee5405a99620a3a240c`; do not silently substitute a different export.

```powershell
New-Item -ItemType Directory -Force .local-models | Out-Null
Invoke-WebRequest 'https://huggingface.co/superwhisper/s1-mini-GGUF/resolve/34add00a48a2e5d24e5a4ee5405a99620a3a240c/s1-mini-f16.gguf' -OutFile .local-models/s1-mini-f16.gguf
Get-FileHash .local-models/s1-mini-f16.gguf -Algorithm SHA256
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama create s1-mini:f16 -f Modelfile
ollama show s1-mini:f16
```

Expected F16 SHA-256:
`0370da4f1bae19e3150bcafa33c5d396c15f97bf25519540a3e013db5cc00af4`.
The default Ollama tokenizer is pinned to the HF baseline revision above; a custom
`SERVICE_MODEL` source must supply the tokenizer matching its imported GGUF.

Ollama must already be running on the host. The tracked `Modelfile` imports the local file,
sets greedy decoding and disables GPU offload. The API also sends `temperature: 0`,
`repeat_penalty: 1`, `num_gpu: 0` and the same token output window as torch on every request.
It renders the **same HF tokenizer's chat template**, `enable_thinking=False`, and sends
that prompt with `raw: true` to `/api/generate`. Ollama's own chat template, SYSTEM text,
thinking mode and default repetition penalty cannot replace the model-card prompt.
No reasoning is stripped from output or held until the whole answer completes.

Context starts at 4096 tokens to avoid reserving the full 40,960-token window for short
transcripts. Each chunk reserves at least its exact rendered prompt count plus its output
budget, so a sentence longer than the chunk limit is still sent whole.

For a local service, use `.env` in this folder (`run.bat` passes `--dotenv`; a plain `python src/app.py` does not read it) or real environment variables (a real variable wins):

```powershell
$env:SERVICE_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:SERVICE_OLLAMA_MODEL = 's1-mini:f16'
$env:SERVICE_NUM_THREAD = '6' # Use your host's physical core count.
uv run src/app.py
```

For Compose set `SERVICE_OLLAMA_URL=http://host.docker.internal:11434` and
`SERVICE_OLLAMA_MODEL=s1-mini:f16` in its environment file. Compose includes the Linux
`host-gateway` mapping. Configure the host Ollama listener to allow the container to reach
it; keep port 11434 on a trusted network. The service still needs the matching HF tokenizer
(small download; `SERVICE_MODEL` selects its source), but does not load torch weights.
Clear the URL and restart to return to torch. A saved URL/model setting takes precedence
over the environment; reset the saved setting too when switching back.

## Threads, replicas and weights

- The CPU threads card applies live to Ollama's `options.num_thread` on the next chunk;
  values propagate to other replicas within about a second. Set the physical core count.
- Ollama owns the loaded GGUF. API replicas retain independent queues and answer caches,
  while Ollama schedules work and owns model memory. More replicas do not guarantee more throughput.
- `dtype` only affects torch. Thinking and temperature are intentionally not user settings.
- Updates compare **local Ollama digests only**, not Hub releases. The Download action
  returns an explicit error directing you to re-import; a local pinned model must not be
  replaced by `ollama pull` from an unrelated registry tag. Re-import with `ollama create`
  and restart every API replica to clear its loaded state and answer cache.
- Cancellation closes the current chunk's response; it never sets the caller's shared
  stop event on ordinary chunk completion. Network I/O stays in engine worker threads;
  read timeouts bound a stalled Ollama connection. Transport failures become `EngineError`.

## Quality and speed gate

Use the same synthetic transcripts and tokenizer revision for both engines. No HTTP answer
cache participates. `chunk_tokens=50` deliberately exercises multiple chunks. Warm-up and
weight loading are excluded; reported output tokens/sec includes prompt evaluation,
decoding and sentence assembly. This is end-to-end throughput, not Ollama's decode-only rate.

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
$env:UV_LINK_MODE = 'copy'
# Fetch the exact HF baseline if not already cached:
uv run hf download superwhisper/s1-mini --revision 88f6b15896c73bbb13a3b596e0afe8ea0d5150b4
uv run tools/compare_backends.py --backend torch --threads 6 --output docs/torch-results.json
uv run tools/compare_backends.py --backend ollama --model s1-mini:f16 --threads 6 --output docs/ollama-results.json
uv run pytest -q
uv run python tools/check_sync.py
```

Compare each `content` and `finish` field in the two JSON reports. Review differences for
lost meaning, repetition, incorrect numbers and changed styling. Stop deployment if output
quality degrades; passing fake-server tests alone does not pass this gate.
