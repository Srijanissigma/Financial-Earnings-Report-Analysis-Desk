from .base_analyst import BaseAnalyst, sentiment_from
from .models import Analysis, Claim


class OutlookAnalyst(BaseAnalyst):
    section = "Outlook"
    agent_name = "Outlook_Analyst"
    role = "Outlook Analyst"
    focus = ("Assess the forward guidance: next-quarter revenue, full-year growth and margin "
             "guidance, and whether it implies acceleration or slowdown versus current results.")
    metrics = ["guide_rev_low", "guide_rev_high", "guide_rev_seq", "guide_fy_growth_low",
               "guide_fy_growth_high", "fy_vs_yoy", "guide_opm_low", "guide_opm_high",
               "op_margin", "revenue", "revenue_yoy"]

    def rules(self, s) -> Analysis:
        g, c = s.get, []
        lo, hi, seq = g("guide_rev_low"), g("guide_rev_high"), g("guide_rev_seq")
        if lo and hi:
            ids, txt, st = [lo.id, hi.id], f"Next-quarter revenue guidance is {lo.display()}-{hi.display()}", "neutral"
            if seq:
                txt += f", implying {seq.display()} sequential growth at the midpoint"
                ids.append(seq.id)
                st = "positive" if seq.value > 0 else "negative"
            c.append(Claim(txt + ".", ids, st))
        fl, fh, d = g("guide_fy_growth_low"), g("guide_fy_growth_high"), g("fy_vs_yoy")
        if fl and fh:
            ids, txt, st = [fl.id, fh.id], f"Full-year growth is guided to {fl.display()}-{fh.display()}", "neutral"
            if d:
                txt += f", {d.display()} vs this quarter's growth at the midpoint"
                ids.append(d.id)
                st = "negative" if d.value < 0 else "positive"
            c.append(Claim(txt + ".", ids, st))
        ol, oh, om = g("guide_opm_low"), g("guide_opm_high"), g("op_margin")
        if ol and oh:
            raised = "raised" in ol.source.lower()
            ids = [ol.id, oh.id]
            txt = f"Operating margin guidance is {ol.display()}-{oh.display()}" + (" (raised)" if raised else "")
            if om:
                txt += f" against {om.display()} this quarter"
                ids.append(om.id)
            c.append(Claim(txt + ".", ids, "positive" if raised else "neutral"))
        sent, score = sentiment_from(c)
        return Analysis(self.section, sent, f"score {score:+d}", c)
