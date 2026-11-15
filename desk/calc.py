"""Derived figures are computed by code (never by the LLM) and get their own
IDs (D1, D2, ...), so every number in the note is traceable."""
from .models import FactStore


def add_derived(s: FactStore) -> None:
    g = s.get
    ni, nip = g("net_income"), g("net_income_prior")
    if ni and nip:
        s.add("ni_growth", (ni.value / nip.value - 1) * 100, "pct_chg", "Net income growth YoY",
              f"Derived: net income {ni.id} vs year-ago {nip.id}", True)
    gm, gmp = g("gross_margin"), g("gross_margin_prior")
    if gm and gmp:
        s.add("gm_change_bps", (gm.value - gmp.value) * 100, "bps", "Gross margin change YoY",
              f"Derived: gross margin {gm.id} minus year-ago {gmp.id}", True)
    lo, hi, rev = g("guide_rev_low"), g("guide_rev_high"), g("revenue")
    if lo and hi and rev:
        mid = (lo.value + hi.value) / 2
        s.add("guide_rev_seq", (mid / rev.value - 1) * 100, "pct_chg",
              "Implied sequential revenue growth (guidance midpoint)",
              f"Derived: midpoint of {lo.id}-{hi.id} vs revenue {rev.id}", True)
    fl, fh, yoy = g("guide_fy_growth_low"), g("guide_fy_growth_high"), g("revenue_yoy")
    if fl and fh and yoy:
        s.add("fy_vs_yoy", (fl.value + fh.value) / 2 - yoy.value, "pp",
              "FY growth guidance midpoint vs current YoY growth",
              f"Derived: midpoint of {fl.id}-{fh.id} minus {yoy.id}", True)
    inv = g("inventory_growth")
    if inv and yoy:
        s.add("inventory_gap", inv.value - yoy.value, "pp", "Inventory growth minus revenue growth",
              f"Derived: inventory {inv.id} minus revenue growth {yoy.id}", True)
