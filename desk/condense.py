"""Shrink a long report to its most relevant sentences before sending it to the
LLM (free-tier APIs reject very large requests). Sentences are kept VERBATIM and
in their original order, so quote verification still works against the full text."""
import os
import re

MAX_CHARS = int(os.getenv("MAX_LLM_CHARS", "9000"))

KEY = re.compile(r"revenue|net income|gross margin|operating margin|margin|earnings per share|\beps\b|"
                 r"cash flow|guidance|outlook|expects?|forecast|raised|lowered|increase|decrease|grew|"
                 r"decline|record|orders|backlog|capital expenditure|inventory|customers?", re.I)
GUIDE = re.compile(r"guidance|outlook|expects?|forecast|projected|anticipate", re.I)
RISK = re.compile(r"\brisks?\b|litigation|investigation|impairment|supply|shortage|headwind|uncertain|"
                  r"restructur|lawsuit|material weakness|restatement|tariff|concentration", re.I)
MONEY_PCT = re.compile(r"\$\s?\d|\d\s?%")
BOILER = re.compile(r"forward-looking|safe harbor|securities and exchange|non-gaap financial measures|"
                    r"reconciliation|adjustments to", re.I)


def _segments(text: str) -> list:
    segs = []
    for line in text.splitlines():
        for s in re.split(r"(?<=[.!?])\s+", line.strip()):
            if len(s) >= 25:
                segs.append(s)
    return segs


def _score(s: str) -> int:
    sc = 0
    sc += 2 if KEY.search(s) else 0
    sc += 3 if GUIDE.search(s) else 0
    sc += 1 if RISK.search(s) else 0
    sc += 2 if MONEY_PCT.search(s) else 0
    sc -= 2 if BOILER.search(s) else 0
    alpha = sum(c.isalpha() for c in s) / max(len(s), 1)
    sc -= 5 if (alpha < 0.2 and not KEY.search(s)) else 0     # number-only table fragments
    sc -= 4 if len(s) > 450 else 0         # long legal boilerplate
    return sc


def condense(report: str, max_chars: int = MAX_CHARS):
    """Returns (text_for_llm, original_chars, kept_chars)."""
    n = len(report)
    if n <= max_chars:
        return report, n, n
    segs = _segments(report)
    keep, total = {0}, len(segs[0]) if segs else 0       # always keep the title line
    ranked = sorted(range(1, len(segs)), key=lambda i: (-_score(segs[i]), i))
    for i in ranked:
        if _score(segs[i]) < 2 or len(segs[i]) > 800:
            continue
        if total + len(segs[i]) + 1 > max_chars:
            continue
        keep.add(i)
        total += len(segs[i]) + 1
    out = "\n".join(segs[i] for i in sorted(keep))
    return out, n, len(out)
