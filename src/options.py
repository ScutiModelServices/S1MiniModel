"""The options the admin page can change. Each can still start from its environment variable; a saved value wins."""

from engine import DEFAULT_MODEL
from ollama_backend import DEFAULT_OLLAMA_MODEL
from settings import Setting

SETTINGS = [
    Setting("update_check_hours", "Check for updates every (hours)", "float", 6.0, "S1MINI_UPDATE_CHECK_HOURS", 0, 720,
            help="0 = only when you press Check now"),
    Setting("max_inflight", "Calls allowed to wait for the model", "int", 0, "S1MINI_MAX_INFLIGHT", 0, 10000,
            help="Per replica; more get 429. 0 = 4"),
    Setting("cache_size", "Answers kept per replica", "int", 256, "S1MINI_CACHE_SIZE", 0, 100000,
            help="The last answers for the same request, sent again without generating. Output is always greedy, so every request is kept. 0 = off"),
    Setting("chunk_tokens", "Input tokens per pass", "int", 800, "S1MINI_CHUNK_TOKENS", 50, 4000,
            help="Longer text is cut at sentence ends and normalized piece by piece. The model card advises staying under about 1000"),
    Setting("model", "Base model", "text", DEFAULT_MODEL, "S1MINI_MODEL", restart=True, blank=False,
            help="A Hugging Face repository. After a restart, download it from the Updates card"),
    Setting("dtype", "Number format", "text", "bfloat16", "S1MINI_DTYPE", restart=True, blank=False,
            help="bfloat16 or float32. float32 is faster on CPUs without native bfloat16 maths but uses twice the memory"),
    Setting("ollama_url", "Host Ollama URL", "text", "", "S1MINI_OLLAMA_URL", restart=True,
            help="Empty uses torch. Docker: http://host.docker.internal:11434; local: http://127.0.0.1:11434"),
    Setting("ollama_model", "Ollama model", "text", DEFAULT_OLLAMA_MODEL, "S1MINI_OLLAMA_MODEL", restart=True,
            help="Pinned local S1-mini GGUF imported with ollama create. Base model still supplies the matching HF tokenizer"),
    Setting("warm", "Load the model at start", "bool", True, "S1MINI_WARM", restart=True),
]
