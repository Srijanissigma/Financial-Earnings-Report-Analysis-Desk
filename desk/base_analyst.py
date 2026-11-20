"""Shared logic for the three analyst agents: LLM first (Semantic Kernel agent),
every claim grounded-checked, rule-based fallback if the LLM fails."""
import json

from .grounding import claim_ok
from .llm import extract_json
from .models import Analysis, Claim

COMMON = (
    "You will receive a JSON list of facts from an earnings report (id, label, value, source). "
    "Reply with ONLY this JSON, no other text:\n"
    '{"sentiment":"positive|negative|neutral","verdict":"<max 8 words>",'
    '"claims":[{"text":"...","fact_ids":["F1"],"stance":"positive|negative|neutral"}]}\n'
    "Rules: write 3 to 6 claims. Every claim must cite at least one fact id. Use ONLY the given facts. "
    "Copy numbers exactly as written in each fact's 'value' (for example $4.82B or +13.3%). "
    "Never calculate, round or invent numbers."
)


def sentiment_from(claims):
    score = sum(c.stance == "positive" for c in claims) - sum(c.stance == "negative" for c in claims)
    return "positive" if score > 0 else "negative" if score < 0 else "neutral", score


class BaseAnalyst:
    section = ""
    agent_name = ""
    role = ""
    focus = ""
    metrics: list = []

    def relevant(self, store):
        return [f for f in store.facts if f.metric in self.metrics]

    def instructions(self):
        return f"You are the {self.role} on an equity research desk. {self.focus} {COMMON}"

    def rules(self, store) -> Analysis:      # overridden by each analyst
        raise NotImplementedError

    async def run(self, store, runner) -> Analysis:
        facts = self.relevant(store)
        result = None
        if runner.available and facts:
            result = await self._llm(store, runner, facts)
        if result is None or not result.claims:
            result = self.rules(store)
            result.mode = "rules"
        return result

    async def _llm(self, store, runner, facts):
        payload = json.dumps([{"id": f.id, "label": f.label, "value": f.display(),
                               "source": f.source} for f in facts])
        data = extract_json(await runner.ask(self.agent_name, self.instructions(), payload, max_tokens=1500))
        if not data:
            return None
        allowed = {f.id for f in facts}
        claims, dropped = [], 0
        for c in data.get("claims", []):
            if not isinstance(c, dict):
                continue
            ids, text = c.get("fact_ids", []), str(c.get("text", "")).strip()
            if text and isinstance(ids, list) and set(ids) <= allowed and claim_ok(text, ids, store):
                stance = c.get("stance", "neutral")
                claims.append(Claim(text, ids, stance if stance in
                                    ("positive", "negative", "neutral") else "neutral"))
            else:
                dropped += 1
        sent = data.get("sentiment")
        if sent not in ("positive", "negative", "neutral"):
            sent = sentiment_from(claims)[0]
        return Analysis(self.section, sent, str(data.get("verdict", sent))[:60], claims, "llm", dropped)
