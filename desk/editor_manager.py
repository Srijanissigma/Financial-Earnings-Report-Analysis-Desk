"""Editor Manager: the coordinator. Runs Extraction, fans out to the three analysts
in parallel, fans their results back in, checks grounding, flags disagreement and
writes the one-page note."""
import asyncio
import re

from .calc import add_derived
from .extraction_agent import ExtractionAgent
from .grounding import allowed_numbers, numbers
from .llm import AgentRunner
from .outlook_analyst import OutlookAnalyst
from .revenue_analyst import RevenueAnalyst
from .risk_analyst import RiskAnalyst

EDITOR_INSTRUCTIONS = (
    "You are the Editor Manager of an equity research desk. You receive verified claims from three "
    "analysts (each ends with its fact ids in brackets) plus any disagreements. Write a 3 sentence "
    "executive summary for an analyst note. Cite fact ids like [F1] after every figure, copy numbers "
    "exactly as written, add no new numbers, and mention any disagreement. Reply with plain text only."
)


class EditorManager:
    def __init__(self):
        self.runner = AgentRunner()
        self.extractor = ExtractionAgent()
        self.workers = [RevenueAnalyst(), RiskAnalyst(), OutlookAnalyst()]
        self.store = None
        self.analyses = []

    async def run(self, report: str) -> str:
        title = report.strip().splitlines()[0]
        self.store = await self.extractor.run(report, self.runner)             # step 1: extract
        add_derived(self.store)                                                # step 2: derive
        self.analyses = list(await asyncio.gather(                             # step 3: FAN-OUT
            *(w.run(self.store, self.runner) for w in self.workers)))
        return await self._fan_in(title)                                       # step 4: FAN-IN

    def _validate(self):
        """Last gate: drop any claim without valid fact references."""
        dropped = sum(a.dropped for a in self.analyses)
        for a in self.analyses:
            keep = [c for c in a.claims if c.fact_ids and all(i in self.store.by_id for i in c.fact_ids)]
            dropped += len(a.claims) - len(keep)
            a.claims = keep
        return dropped

    def _disagreements(self):
        s, out = self.store, []
        pos = [a for a in self.analyses if a.sentiment == "positive"]
        neg = [a for a in self.analyses if a.sentiment == "negative"]
        if pos and neg:
            out.append("Analysts disagree: " + "; ".join(f"{a.section} is {a.sentiment}"
                       for a in pos + neg) + ".")
        gm, gmp, oh, om = s.get("gross_margin"), s.get("gross_margin_prior"), s.get("guide_opm_high"), s.get("op_margin")
        if gm and gmp and oh and om and gm.value < gmp.value and oh.value > om.value:
            out.append(f"Margin tension: gross margin fell ({gmp.display()} to {gm.display()}) yet operating "
                       f"margin guidance reaches {oh.display()} vs {om.display()} now "
                       f"[{gm.id}, {gmp.id}, {oh.id}, {om.id}].")
        return out

    async def _summary(self, dis):
        by = {a.section: a for a in self.analyses}
        risk_level = {"negative": "elevated", "neutral": "moderate", "positive": "low"}[by["Risk"].sentiment]
        fallback = (f"Revenue is {by['Revenue'].sentiment}, risk is {risk_level}, "
                    f"and the outlook is {by['Outlook'].sentiment}.")
        if not self.runner.available:
            return fallback, "rules"
        body = "\n".join(f"{c.text} [{', '.join(c.fact_ids)}]" for a in self.analyses for c in a.claims)
        text = await self.runner.ask("Editor_Manager", EDITOR_INSTRUCTIONS,
                                     body + "\nDisagreements: " + (" ".join(dis) or "none"))
        if not text:
            print("[editor] no summary returned, using the template summary")
            return fallback, "rules"
        bad_ids = set(re.findall(r"\b[FD]\d+\b", text)) - set(self.store.by_id)
        clean_text = re.sub(r"\[[FD]\d+(?:\s*,\s*[FD]\d+)*\]", "", text)
        bad_nums = numbers(clean_text) - allowed_numbers(self.store.facts)
        if bad_nums:
            print("[editor] AI summary:", repr(text))
            print("[editor] Unsupported numbers:", sorted(bad_nums))
        if not bad_ids and not bad_nums:
            return text.strip(), "llm"
        print(f"[editor] summary rejected (unknown ids: {sorted(bad_ids)}, "
              f"ungrounded numbers: {sorted(bad_nums)}); using the template summary")
        return fallback, "rules"

    async def _fan_in(self, title):
        dropped = self._validate()
        dis = self._disagreements()
        summary, smode = await self._summary(dis)
        L = [f"# Analyst Note: {title}", "", f"**Summary.** {summary}", ""]
        used = []
        for a in self.analyses:
            L.append(f"## {a.section}: {a.sentiment} ({a.verdict})")
            for c in a.claims:
                L.append(f"- {c.text} [{', '.join(c.fact_ids)}]")
                used += [i for i in c.fact_ids if i not in used]
            L.append("")
        L.append("## Flagged disagreements")
        L += [f"- {d}" for d in dis] or ["- None; the three analyses are consistent."]
        L += ["", "## Sources (every figure traces to the report)",
              "| ID | Figure | Value | Report sentence / derivation |", "|---|---|---|---|"]
        for i in sorted(used, key=lambda x: (x[0], int(x[1:]))):
            f = self.store.by_id[i]
            L.append(f"| {i} | {f.label} | {f.display()} | {f.source} |")
        modes = ", ".join(f"{a.section}: {a.mode}" for a in self.analyses)
        L += ["", f"_Run log: extraction: {self.store.mode} ({self.store.rejected} figures rejected by "
                  f"verification); analysts: {modes}; editor summary: {smode}; "
                  f"ungrounded claims removed: {dropped}; model: {self.runner.model_used or 'none (offline rules)'}._"]
        return "\n".join(L)
