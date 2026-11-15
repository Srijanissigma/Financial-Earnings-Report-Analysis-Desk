from .base_analyst import BaseAnalyst, sentiment_from
from .models import Analysis, Claim


class RevenueAnalyst(BaseAnalyst):
    section = "Revenue"
    agent_name = "Revenue_Analyst"
    role = "Revenue Analyst"
    focus = ("Comment on revenue, growth, segment performance, profit and margins, always "
             "with the figures behind each point.")
    metrics = ["revenue", "revenue_yoy", "cloud_growth", "net_income", "net_income_prior", "ni_growth",
               "gross_margin", "gross_margin_prior", "gm_change_bps", "op_margin", "eps"]

    def rules(self, s) -> Analysis:
        g, c = s.get, []
        rev, yoy, cloud = g("revenue"), g("revenue_yoy"), g("cloud_growth")
        if rev and yoy:
            c.append(Claim(f"Revenue was {rev.display()}, up {yoy.display()} year over year.",
                           [rev.id, yoy.id], "positive" if yoy.value >= 5 else "negative" if yoy.value < 0 else "neutral"))
        if cloud:
            c.append(Claim(f"Cloud segment grew {cloud.display()}.", [cloud.id],
                           "positive" if cloud.value > (yoy.value if yoy else 0) else "neutral"))
        ni, nip, gr = g("net_income"), g("net_income_prior"), g("ni_growth")
        if ni and nip and gr:
            c.append(Claim(f"Net income was {ni.display()} vs {nip.display()} a year ago ({gr.display()}).",
                           [ni.id, nip.id, gr.id], "positive" if gr.value > 0 else "negative"))
        gm, gmp, bps = g("gross_margin"), g("gross_margin_prior"), g("gm_change_bps")
        if gm and gmp and bps:
            c.append(Claim(f"Gross margin was {gm.display()}, {bps.display()} vs {gmp.display()} a year ago.",
                           [gm.id, gmp.id, bps.id], "positive" if bps.value > 0 else "negative" if bps.value < 0 else "neutral"))
        om, eps = g("op_margin"), g("eps")
        if om:
            c.append(Claim(f"Operating margin was {om.display()}.", [om.id]))
        if eps:
            c.append(Claim(f"Diluted EPS was {eps.display()}.", [eps.id]))
        sent, score = sentiment_from(c)
        return Analysis(self.section, sent, f"score {score:+d}", c)
