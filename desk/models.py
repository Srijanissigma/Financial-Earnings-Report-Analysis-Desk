from dataclasses import dataclass, field


@dataclass
class Fact:
    id: str                 # F1.. = extracted from report, D1.. = derived by code
    metric: str
    value: float | None
    unit: str               # USD_m | pct | usd | pct_chg | bps | pp | text
    label: str
    source: str             # exact report sentence (or the derivation formula)
    derived: bool = False

    def display(self) -> str:
        v, u = self.value, self.unit
        if u == "USD_m":
            return f"${v/1000:.2f}B" if abs(v) >= 1000 else f"${v:,.0f}M"
        if u == "pct":
            return f"{v:.1f}%"
        if u == "usd":
            return f"${v:.2f}"
        if u == "pct_chg":
            return f"{v:+.1f}%"
        if u == "bps":
            return f"{v:+.0f} bps"
        if u == "pp":
            return f"{v:+.1f} pp"
        return self.label


class FactStore:
    """Shared memory (blackboard) that every agent reads from."""

    def __init__(self):
        self.facts: list[Fact] = []
        self.by_id: dict[str, Fact] = {}
        self.mode = "rules"          # how extraction was done: llm | rules
        self.condensed = None        # (original chars, chars sent to the LLM)
        self.rejected = 0            # LLM figures that failed verification
        self._n = {"F": 0, "D": 0}

    def add(self, metric, value, unit, label, source, derived=False) -> Fact:
        p = "D" if derived else "F"
        self._n[p] += 1
        f = Fact(f"{p}{self._n[p]}", metric, value, unit, label, source, derived)
        self.facts.append(f)
        self.by_id[f.id] = f
        return f

    def get(self, metric):
        return next((f for f in self.facts if f.metric == metric), None)

    def flags(self):
        return [f for f in self.facts if f.metric == "risk_flag"]


@dataclass
class Claim:
    text: str
    fact_ids: list
    stance: str = "neutral"      # positive | negative | neutral


@dataclass
class Analysis:
    section: str
    sentiment: str               # positive | negative | neutral
    verdict: str
    claims: list = field(default_factory=list)
    mode: str = "rules"          # llm | rules
    dropped: int = 0             # ungrounded claims removed from this analysis
