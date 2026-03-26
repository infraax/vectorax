"""
Local LLM dispatch — routes simple questions to qwen2.5-coder:7b via Ollama.

Use this instead of burning Anthropic tokens on:
  - "What does this function do?"
  - "Generate a stub for this gRPC handler"
  - "Is this proto change backward-compatible?"
  - "Summarize these 3 code chunks"

Claude escalates to itself only for architecture decisions and cross-repo reasoning.
"""
import json
import urllib.request
import urllib.error

OLLAMA_URL   = "http://127.0.0.1:11434"
CODER_MODEL  = "qwen2.5-coder:7b"
DEFAULT_MODEL = "qwen2.5:14b"   # fallback for non-code questions


def ask(
    question: str,
    context: str = "",
    model: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.1,
) -> str:
    """
    Ask a local Ollama model a question, optionally with code context.
    Returns the model's response string, or an error message.
    """
    chosen_model = model or CODER_MODEL

    prompt = question
    if context.strip():
        prompt = f"Context:\n```\n{context.strip()[:3000]}\n```\n\nQuestion: {question}"

    payload = json.dumps({
        "model":   chosen_model,
        "prompt":  prompt,
        "stream":  False,
        "options": {
            "temperature":    temperature,
            "num_predict":    max_tokens,
            "num_ctx":        4096,
        },
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        return f"[local_llm error: Ollama unreachable — {e}]"
    except Exception as e:
        return f"[local_llm error: {e}]"


def embed(texts: list[str]) -> list[list[float]]:
    """
    Batch embed texts using nomic-embed-text.
    Returns list of 768-dim vectors.
    """
    if not texts:
        return []
    payload = json.dumps({
        "model": "nomic-embed-text",
        "input": [t[:4096] for t in texts],
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()).get("embeddings", [])
    except Exception:
        return [[] for _ in texts]


def available_models() -> list[str]:
    """Return list of currently loaded Ollama models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
