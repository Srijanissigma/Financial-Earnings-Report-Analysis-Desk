"""Settings. Reads .env (GROQ_API_KEY, GROQ_MODEL)."""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
_key = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_KEY = "" if (not _key or "paste" in _key.lower()) else _key

# Tried in order. If a model is retired or rate-limited, the next one is used.
PREFERRED_MODELS = [m for m in dict.fromkeys(
    [os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(), "openai/gpt-oss-120b"]) if m]
