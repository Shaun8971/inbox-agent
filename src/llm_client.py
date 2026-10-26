"""LLM access through the Open WebUI gateway (Anthropic Messages format).

One place for the connection, so every LLM call in the project is made, timed, and measured the same way.

EVERY EXPLANATION ABOUT THIS IS IN 00_gateway_test.ipynb
"""
import os
import time
import anthropic
from dotenv import load_dotenv
from src.config import ROOT

# Load secrets from .env in the project root (works no matter where the code is run from)
load_dotenv(ROOT / ".env")


def get_client():
    """Return a client connected to the gateway, using the secrets in .env."""
    return anthropic.Anthropic(
        api_key=os.getenv("OPENWEBUI_API_KEY"),     # Your ID badge
        base_url=os.getenv("OPENWEBUI_BASE_URL"),   # Where to send requests
    )


def call_llm(client, model, system, user, max_tokens=300):
    """Send one request and return (reply_text, info).

    system = the instructions (our prompt)
    user   = the content to work on (e.g. one email)
    info   = latency and token counts, for cost and speed tracking
    """
    start = time.perf_counter()   # Stopwatch on
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    usage = response.usage
    # With caching, Anthropic splits input into three parts; the real input is their sum.
    # getattr(..., 0) reads a field if it exists, otherwise uses 0 (some gateways may omit it).
    # "or 0" turns a None value into 0, so the addition below never fails.
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    info = {
        "latency_s": round(time.perf_counter() - start, 2),
        "input_tokens": usage.input_tokens + cache_write + cache_read,   # Total input actually processed
        "cache_write_tokens": cache_write,   # Written to the cache this call
        "cache_read_tokens": cache_read,     # Reused from the cache (much cheaper)
        "output_tokens": usage.output_tokens,
    }
    # A reply can contain several blocks; join the text ones (usually there's just one)
    text = "".join(block.text for block in response.content if block.type == "text")
    return text, info