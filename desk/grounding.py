"""Grounding checks. A claim survives only if it cites real fact IDs and every
number in its text appears in the cited facts (value or source sentence)."""
import re

NUM = re.compile(r"(?<![A-Za-z])\d[\d,]*\.?\d*")


def numbers(text: str) -> set:
    out = set()
    for t in NUM.findall(text):
        t = t.replace(",", "").rstrip(".")
        try:
            out.add(round(float(t), 4))
        except ValueError:
            pass
    return out


def allowed_numbers(facts) -> set:
    s = set()
    for f in facts:
        s |= numbers(f.display()) | numbers(f.source)
    return s


def claim_ok(text: str, ids: list, store) -> bool:
    if not ids or not all(i in store.by_id for i in ids):
        return False
    cited = [store.by_id[i] for i in ids]
    return numbers(text) <= allowed_numbers(cited)
