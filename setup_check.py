"""Run this first: python setup_check.py"""
import asyncio
import sys

print(f"Python {sys.version.split()[0]}", "OK" if sys.version_info >= (3, 10) else "-> need 3.10+")
for pkg in ("semantic_kernel", "openai", "dotenv"):
    try:
        __import__(pkg)
        print(f"{pkg}: OK")
    except ImportError:
        print(f"{pkg}: MISSING -> pip install -r requirements.txt")

from desk.config import GROQ_API_KEY, PREFERRED_MODELS
print("GROQ_API_KEY:", "found" if GROQ_API_KEY else "NOT SET (put it in .env). Offline rules mode will be used.")
print("Models (in order):", PREFERRED_MODELS)

if GROQ_API_KEY:
    from desk.llm import AgentRunner
    r = AgentRunner()
    reply = asyncio.run(r.ask("Ping_Agent", "Reply with the single word OK.", "ping"))
    print("Groq test:", f"OK via {r.model_used}" if reply else f"FAILED -> {r.last_error}")
