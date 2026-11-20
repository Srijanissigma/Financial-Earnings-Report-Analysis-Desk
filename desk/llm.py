"""Semantic Kernel agent runner on Groq (OpenAI-compatible endpoint).
Every agent is a Semantic Kernel ChatCompletionAgent. Models in PREFERRED_MODELS
are tried in order, with retries for free-tier rate limits."""
import asyncio
import json
import os
import re

from .config import GROQ_API_KEY, GROQ_BASE_URL, PREFERRED_MODELS


def extract_json(text: str | None):
    """Pull the first JSON object out of a model reply (handles ``` fences)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        return None


class AgentRunner:
    def __init__(self):
        self.services = []
        self.last_error = None
        self.model_used = None
        if not GROQ_API_KEY:
            return
        from openai import AsyncOpenAI
        from semantic_kernel.connectors.ai.open_ai import (
            OpenAIChatCompletion, OpenAIChatPromptExecutionSettings)
        from semantic_kernel.functions import KernelArguments
        client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        # Semantic Kernel adds a "name" field to messages; strip it so strict
        # OpenAI-compatible APIs (like Groq) never reject the request.
        _create = client.chat.completions.create

        async def _create_no_names(*a, **kw):
            kw["messages"] = [{k: v for k, v in m.items() if k != "name"}
                              for m in kw.get("messages", [])]
            return await _create(*a, **kw)

        client.chat.completions.create = _create_no_names
        for m in PREFERRED_MODELS:
            self.services.append((m, OpenAIChatCompletion(ai_model_id=m, async_client=client)))
        self._Settings, self._Args = OpenAIChatPromptExecutionSettings, KernelArguments
        # low reasoning keeps replies short and cheap on the free tier ("" to disable)
        self.effort = os.getenv("GROQ_REASONING_EFFORT", "low").strip() or None

    def _args(self, max_tokens):
        kw = dict(temperature=0.1, max_tokens=max_tokens)
        if self.effort:
            kw["reasoning_effort"] = self.effort
        return self._Args(settings=self._Settings(**kw))

    @property
    def available(self) -> bool:
        return bool(self.services)

    async def ask(self, name: str, instructions: str, message: str, max_tokens: int = 1500) -> str | None:
        """Run one Semantic Kernel agent. Returns text or None.
        413 (request too large): give up on this model. 429 (rate limit): wait, then retry."""
        from semantic_kernel.agents import ChatCompletionAgent
        for model, svc in self.services:
            for attempt in range(3):
                try:
                    agent = ChatCompletionAgent(service=svc, name=name, instructions=instructions)
                    resp = await agent.get_response(messages=message, arguments=self._args(max_tokens))
                    text = str(resp.message.content).strip()
                    if text:
                        self.model_used = model
                        return text
                    break                                   # empty reply: try next model
                except Exception as e:
                    msg = str(e)
                    self.last_error = f"{model}: {type(e).__name__}: {msg[:200]}"
                    print(f"[llm] {name} {self.last_error}")
                    if "reasoning" in msg.lower() and self.effort:
                        self.effort = None                  # API rejected the option: drop it
                        continue
                    if "413" in msg:
                        break                               # too large: retrying will not help
                    if "429" in msg or "rate limit" in msg.lower():
                        m = re.search(r"try again in ([\d.]+)(ms|s)", msg)
                        wait = (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) + 1) if m else 8 * (attempt + 1)
                        await asyncio.sleep(min(wait, 30))
                    else:
                        await asyncio.sleep(2)
            print(f"[llm] {model} failed for {name}, trying next model")
        return None
