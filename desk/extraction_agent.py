"""Extraction Agent. Structured extraction: a Semantic Kernel agent returns JSON
figures with the exact report sentence for each. Every figure is VERIFIED in code
(quote must exist in the report and contain the number). If the LLM is
unavailable or too few figures verify, a regex extractor is used instead."""
import re

from .llm import extract_json
from .models import FactStore

N = r"(\d[\d,]*(?:\.\d+)?)"
MONEY = r"\$" + N + r"\s*(billion|million)"


def _usd(m):
    v = float(m.group(1).replace(",", ""))
    return v * 1000 if m.group(2).lower() == "billion" else v


def _num(m):
    return float(m.group(1).replace(",", ""))


# metric, label, unit, sentence_gate, value_regex, converter
RULES = [
    ("revenue", "Revenue (quarter)", "USD_m", r"^(Total )?revenue\b", MONEY, _usd),
    ("revenue_yoy", "Revenue growth YoY", "pct", r"^(Total )?revenue\b", r"up " + N + "%", _num),
    ("net_income", "Net income", "USD_m", r"^Net income", MONEY, _usd),
    ("net_income_prior", "Net income (year-ago)", "USD_m", r"^Net income", r"compared with " + MONEY, _usd),
    ("gross_margin", "Gross margin", "pct", r"^Gross margin", r"was " + N + "%", _num),
    ("gross_margin_prior", "Gross margin (year-ago)", "pct", r"^Gross margin", r"from " + N + "%", _num),
    ("op_margin", "Operating margin", "pct", r"^Operating margin", r"was " + N + "%", _num),
    ("eps", "Diluted EPS", "usd", r"^Diluted EPS", r"\$" + N, _num),
    ("cloud_growth", "Cloud segment growth", "pct", r"^Cloud segment", r"grew " + N + "%", _num),
    ("inventory_growth", "Inventory growth", "pct", r"^Inventory", r"(?:increased|rose) " + N + "%", _num),
    ("fcf_change", "Free cash flow change", "pct", r"^Free cash flow", r"(?:decreased|fell) " + N + "%",
     lambda m: -_num(m)),
    ("customer_conc", "Top-3 customer share of revenue", "pct", r"top three customers", N + "%", _num),
    ("fx_headwind", "FX headwind", "USD_m", r"currency headwind", MONEY, _usd),
    ("guide_rev_low", "Next-quarter revenue guidance (low)", "USD_m", r"expects revenue", r"of " + MONEY, _usd),
    ("guide_rev_high", "Next-quarter revenue guidance (high)", "USD_m", r"expects revenue", r"to " + MONEY, _usd),
    ("guide_fy_growth_low", "FY revenue growth guidance (low)", "pct", r"full-year revenue growth",
     r"growth of " + N + "%", _num),
    ("guide_fy_growth_high", "FY revenue growth guidance (high)", "pct", r"full-year revenue growth",
     r"to " + N + "%", _num),
    ("guide_opm_low", "FY operating margin guidance (low)", "pct", r"guidance for operating margin",
     r"margin to " + N + "%", _num),
    ("guide_opm_high", "FY operating margin guidance (high)", "pct", r"guidance for operating margin",
     r"% to " + N + "%", _num),
]
META = {m: (label, unit) for m, label, unit, *_ in RULES}
RISK_WORDS = ["litigation", "investigation", "material weakness", "restatement",
              "impairment", "going concern", "supply chain", "recall"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _quote_supports(value, quote) -> bool:
    """The number must really appear in the quote (also as billions->millions)."""
    for t in re.findall(r"\d[\d,]*\.?\d*", quote):
        try:
            n = float(t.replace(",", "").rstrip("."))
        except ValueError:
            continue
        if any(abs(abs(value) - c) < 1e-6 * max(1, c) for c in (n, n * 1000)):
            return True
    return False


class ExtractionAgent:
    name = "Extraction_Agent"

    INSTRUCTIONS = (
        "You are the Extraction Agent on an equity research desk. Read the earnings report "
        "and extract key figures as JSON ONLY, no other text:\n"
        '{"figures":[{"metric":"<key>","value":<number>,"quote":"<exact sentence from the report>"}],'
        '"risk_flags":[{"label":"<2-4 words>","quote":"<exact sentence from the report>"}]}\n'
        "Allowed metric keys and units (dollar values must be in millions of USD, percentages as plain "
        "numbers such as 12.4, EPS in dollars):\n"
        + "\n".join(f"- {m}: {META[m][0]} [{META[m][1]}]" for m in META)
        + "\nFor fcf_change use a negative number if free cash flow fell. "
        "Copy the quote EXACTLY from the report. Only extract figures that are stated; never guess. "
        "risk_flags are sentences describing litigation, supply problems, investigations, impairments etc."
    )

    async def run(self, report: str, runner) -> FactStore:
        store = FactStore()
        if runner.available:
            raw = await runner.ask(self.name, self.INSTRUCTIONS, report)
            data = extract_json(raw)
            if data and self._load(store, data, report) >= 5:
                store.mode = "llm"
                return store
            store = FactStore()           # discard partial result, use rules
        self._rules(store, report)
        return store

    def _load(self, store, data, report) -> int:
        rep, seen = _norm(report), set()
        for item in data.get("figures", []):
            try:
                metric, value, quote = item["metric"], float(item["value"]), str(item["quote"])
            except (KeyError, TypeError, ValueError):
                store.rejected += 1
                continue
            if metric not in META or metric in seen or _norm(quote) not in rep \
                    or not _quote_supports(value, quote):
                store.rejected += 1
                continue
            seen.add(metric)
            label, unit = META[metric]
            store.add(metric, value, unit, label, quote.strip())
        for item in data.get("risk_flags", [])[:6]:
            quote = str(item.get("quote", "")) if isinstance(item, dict) else ""
            if _norm(quote) and _norm(quote) in rep:
                store.add("risk_flag", None, "text", str(item.get("label", "risk"))[:40], quote.strip())
            else:
                store.rejected += 1
        return len(seen)

    def _rules(self, store, report):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", report) if s.strip()]
        for metric, label, unit, gate, rx, fn in RULES:
            for s in sents:
                if re.search(gate, s, re.I):
                    m = re.search(rx, s, re.I)
                    if m:
                        store.add(metric, fn(m), unit, label, s)
                        break
        seen = set()
        for s in sents:
            for w in RISK_WORDS:
                if w in s.lower() and w not in seen:
                    seen.add(w)
                    store.add("risk_flag", None, "text", f"{w} disclosed", s)
