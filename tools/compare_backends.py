"""Compare uncached CPU normalization on fixed synthetic transcripts.

Example: uv run tools/compare_backends.py --backend torch --output docs/torch-results.json
Then run with --backend ollama --output docs/ollama-results.json. Warm-up is excluded;
throughput includes prompt evaluation, decoding and sentence assembly, not model loading.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine import S1MiniEngine
from ollama_backend import OllamaLoaded

HF_REVISION = "88f6b15896c73bbb13a3b596e0afe8ea0d5150b4"
GGUF_REVISION = "34add00a48a2e5d24e5a4ee5405a99620a3a240c"
SAMPLES = [
    ("correction", "so um i need to like send the the report by uh friday no wait make that thursday", "semi-formal", "prose", "general"),
    ("numbers", "the total is twenty five dollars and fifty cents and we need three copies by two thirty pm", "semi-formal", "prose", "general"),
    ("email", "hey sarah um can you send me the updated budget by tomorrow thanks john", "formal", "prose", "email"),
    ("lists", "we need milk eggs and bread also pick up some coffee", "semi-formal", "lists", "general"),
    ("casual", "yeah um i think we should probably go with the blue one no the green one", "casual", "prose", "general"),
    ("semi-casual", "hey so uh i finished the draft and i will send it over in ten minutes", "semi-casual", "prose", "general"),
    ("fillers", "um uh um", "semi-formal", "prose", "general"),
    ("email-address", "send it to jane dot doe at example dot com please", "semi-formal", "prose", "general"),
    ("punctuation", "are you coming tomorrow i hope so please let me know", "formal", "prose", "general"),
    ("unicode", "um the café on josé street is open until six pm", "semi-formal", "prose", "general"),
    ("multichunk", "so um we met with the team on monday. the budget is five hundred dollars no six hundred dollars. "
     "please send the report by friday. we need three copies for the meeting. "
     "uh the next review is at ten thirty on tuesday. thanks everyone for your help.", "semi-formal", "prose", "general"),
    ("multichunk-lists", "first uh buy five notebooks. next get two pens no three pens. "
     "then send the receipt to sarah. finally um call the office by four pm.", "formal", "lists", "general"),
]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("torch", "ollama"), required=True)
    parser.add_argument("--model", default="s1-mini:f16")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--dtype", default="bfloat16", choices=("bfloat16", "float32"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from huggingface_hub import snapshot_download

    source = await asyncio.to_thread(snapshot_download, "superwhisper/s1-mini", revision=HF_REVISION,
                                     local_files_only=True, token=False)
    options = {}
    if args.backend == "ollama":
        from transformers import AutoTokenizer

        tokenizer = await asyncio.to_thread(AutoTokenizer.from_pretrained, source)
        options = {"loader": lambda _: OllamaLoaded(args.url, args.model, tokenizer, threads=lambda: args.threads),
                   "set_threads": lambda _: None}
    engine = S1MiniEngine(source, dtype=args.dtype, chunk_tokens=50, **options)
    engine.num_thread = args.threads
    await engine.warm()
    await engine.normalize("hello there", "semi-formal", "prose", "general")
    report = {"backend": args.backend, "model": args.model if options else "superwhisper/s1-mini",
              "hf_revision": HF_REVISION, "gguf_revision": GGUF_REVISION if options else None,
              "threads": args.threads, "dtype": args.dtype if not options else "GGUF",
              "chunk_tokens": 50, "samples": []}
    try:
        for name, text, styling, structure, context in SAMPLES:
            started = time.perf_counter()
            reply = await engine.normalize(text, styling, structure, context)
            seconds = time.perf_counter() - started
            row = {"name": name, "text": text, "styling": styling, "structure": structure, "context": context,
                   **reply, "seconds": round(seconds, 4),
                   "tokens_per_second": round(reply["completion_tokens"] / seconds, 3)}
            report["samples"].append(row)
            await asyncio.to_thread(args.output.write_text, json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
            print(f"{name}: {row['tokens_per_second']} tok/s; {reply['content']!r}", flush=True)
        report["tokens_per_second"] = round(sum(row["completion_tokens"] for row in report["samples"]) /
                                            sum(row["seconds"] for row in report["samples"]), 3)
        await asyncio.to_thread(args.output.write_text, json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(f"Overall: {report['tokens_per_second']} tok/s", flush=True)
    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
