"""Semantic Kernel agent runner on Groq (OpenAI-compatible endpoint).
Every agent is a Semantic Kernel ChatCompletionAgent. Models in PREFERRED_MODELS
are tried in order, with retries for free-tier rate limits."""
import asyncio
import json
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
        self._args = KernelArguments(settings=OpenAIChatPromptExecutionSettings(
            temperature=0.1, max_tokens=3000))

    @property
    def available(self) -> bool:
        return bool(self.services)

    async def ask(self, name: str, instructions: str, message: str) -> str | None:
        """Run one Semantic Kernel agent once. Returns text or None."""
        from semantic_kernel.agents import ChatCompletionAgent
        for model, svc in self.services:
            for attempt in range(2):
                try:
                    agent = ChatCompletionAgent(service=svc, name=name, instructions=instructions)
                    resp = await agent.get_response(messages=message, arguments=self._args)
                    text = str(resp.message.content).strip()
                    if text:
                        self.model_used = model
                        return text
                except Exception as e:
                    self.last_error = f"{model}: {type(e).__name__}: {str(e)[:200]}"
                    print(f"[llm] {name} {self.last_error}")
                    await asyncio.sleep(2 * (attempt + 1))
            print(f"[llm] {model} failed for {name}, trying next model")
        return None
