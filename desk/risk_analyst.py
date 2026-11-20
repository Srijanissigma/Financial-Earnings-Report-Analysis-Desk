from .base_analyst import BaseAnalyst
from .models import Analysis, Claim


class RiskAnalyst(BaseAnalyst):
    section = "Risk"
    agent_name = "Risk_Analyst"
    role = "Risk Analyst"
    focus = ("Identify risks and red flags: customer concentration, inventory and cash flow "
             "warnings, currency effects and any risk sentences in the report. Stance for a risk "
             "is 'negative'. Sentiment 'negative' means risk is elevated, 'positive' means low risk.")
    metrics = ["customer_conc", "inventory_growth", "inventory_gap", "revenue_yoy", "fcf_change",
               "fx_headwind", "risk_flag", "rpo_growth", "rpo_gap"]

    def rules(self, s) -> Analysis:
        g, c = s.get, []
        conc = g("customer_conc")
        if conc and conc.value >= 25:
            c.append(Claim(f"Customer concentration is high: top three customers are {conc.display()} of revenue.",
                           [conc.id], "negative"))
        inv, yoy, gap = g("inventory_growth"), g("revenue_yoy"), g("inventory_gap")
        if inv and yoy and gap and gap.value > 0:
            c.append(Claim(f"Inventory grew {inv.display()} against revenue growth of {yoy.display()} "
                           f"({gap.display()} gap), a possible demand warning.", [inv.id, yoy.id, gap.id], "negative"))
        fcf = g("fcf_change")
        if fcf and fcf.value < 0:
            c.append(Claim(f"Free cash flow fell {abs(fcf.value):.1f}%.", [fcf.id], "negative"))
        rpo, rgap = g("rpo_growth"), g("rpo_gap")
        if rpo and yoy and rgap and rgap.value < -5:
            c.append(Claim(f"Backlog (remaining performance obligations) grew {rpo.display()} against revenue "
                           f"growth of {yoy.display()} ({rgap.display()} gap), so future growth may slow.",
                           [rpo.id, yoy.id, rgap.id], "negative"))
        fx = g("fx_headwind")
        if fx:
            c.append(Claim(f"Currency created a {fx.display()} headwind.", [fx.id], "negative"))
        for f in s.flags():
            c.append(Claim(f"Report flags {f.label}: \"{f.source}\"", [f.id], "negative"))
        n = sum(x.stance == "negative" for x in c)
        level = "elevated" if n >= 4 else "moderate" if n >= 2 else "low"
        sent = {"elevated": "negative", "moderate": "neutral", "low": "positive"}[level]
        return Analysis(self.section, sent, f"{level}, {n} red flags", c)
