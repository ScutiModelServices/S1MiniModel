# CPU backend comparison — 2026-11-05

Quality gate passed on the synthetic corpus: all **12/12 cleaned outputs match exactly**
between torch and Ollama F16, including Unicode, empty filler-only output, email layout,
all four styling values, lists and forced multi-chunk normalization. Finish reasons match.
This establishes parity on these samples, not on every possible transcript.

| Backend | Output tokens/sec | Relative speed | Runtime model memory |
|---|---:|---:|---|
| torch 2.15.0+cpu, transformers 5.22.1, bfloat16 | 9.169 | 1.00× | Not measured |
| Host Ollama 0.40.3, official F16 GGUF | 17.097 | 1.86× | About 2.0 GB reported by `ollama ps` |

Machine: AMD Ryzen 7 7445HS, 6 physical cores, 12 logical processors, Windows.
Both engines use **6 CPU threads**. Ollama reports **100% CPU**, 4096 context; `num_gpu=0`.
No GPU acceleration, HTTP answer cache, model loading or warm-up enters these throughput figures.
Throughput is total generated output tokens / total normalization wall time across the corpus,
including prompt evaluation, decoding, tokenization and sentence assembly. Each backend ran
sequentially. One measured pass each; these figures are not a statistical performance guarantee.

`chunk_tokens=50` forces multi-chunk coverage without requiring huge transcripts. Production
default remains 800. Output window, fixed prompt/control line and greedy decoding are unchanged.
The official Q4_K_M export was downloaded but **not imported, benchmarked or quality-approved**.
F16 is the documented/default import because it avoids additional quantization loss.

An initial 40,960-context Ollama run also matched all outputs, but used 6.5 GB and achieved
14.863 tok/s. The final implementation reserves 4096 context for short chunks and grows it
to fit the exact prompt plus output budget for long sentences. Final figures above reflect
that implementation, with no output changes.

Exact transcripts, settings, outputs, token counts and individual elapsed times:

- [torch results](torch-results.json)
- [Ollama F16 results](ollama-results.json)
- [Commands, pinned revisions and GGUF SHA-256](ollama.md)
- [Reproduction script](../tools/compare_backends.py)

The original repo did not pin an HF revision. The comparison explicitly uses cached HF
`88f6b15896c73bbb13a3b596e0afe8ea0d5150b4` and official GGUF repository revision
`34add00a48a2e5d24e5a4ee5405a99620a3a240c`. Default Ollama tokenizer is pinned to that HF
revision; existing torch update behavior still follows its selected Hub source.

Unverified: production Docker-to-host routing, a Docker image build (Dockerfile/dependencies
unchanged), Q4 quality/speed, performance on the deployment server, and generalization beyond
these synthetic samples. Compose configuration was validated without reading `.env`.
Transport timeout/broken-stream failures are explicit `EngineError`s rather than successful
partial answers; cancellation may wait for the next received line or configured read timeout.
