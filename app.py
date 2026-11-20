"""Web app: streamlit run app.py"""
import asyncio
import os

import streamlit as st

# On Streamlit Cloud the key comes from Secrets; locally it comes from .env
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

from desk.editor_manager import EditorManager  # noqa: E402 (after the key is set)
from desk.reader import pdf_to_text  # noqa: E402

def md_table(rows):
    """Markdown table: avoids st.dataframe, which needs pandas (blocked on some Windows setups)."""
    if not rows:
        return "_No data_"
    cols = list(rows[0])
    clean = lambda v: str(v).replace("|", "/").replace("\n", " ")
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(clean(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


st.set_page_config(page_title="Earnings Analysis Desk", layout="wide")
st.title("Financial Earnings Report Analysis Desk")
st.caption("Extraction agent -> Revenue / Risk / Outlook analysts (parallel) -> Editor Manager. "
           "Every figure in the note traces to the report.")

with open("data/sample_report.txt", encoding="utf-8") as f:
    sample = f.read()

upload = st.file_uploader("Upload a report (.txt or .pdf)", type=["txt", "pdf"])
report = sample
if upload:
    try:
        raw = upload.read()
        report = pdf_to_text(raw) if upload.name.lower().endswith(".pdf") else raw.decode("utf-8", "ignore")
    except Exception as e:
        st.error(f"Could not read the file: {e}")
report = st.text_area("Report text (first line = title)", value=report, height=260)

if st.button("Analyze report", type="primary"):
    with st.spinner("Agents are working..."):
        desk = EditorManager()
        note = asyncio.run(desk.run(report))
    t1, t2, t3 = st.tabs(["Analyst note", "Extracted figures", "Agent run"])
    with t1:
        st.markdown(note)
        st.download_button("Download note (.md)", note, "analyst_note.md")
    with t2:
        st.markdown(md_table([{"ID": f.id, "Figure": f.label, "Value": f.display(), "Source": f.source}
                              for f in desk.store.facts]))
    with t3:
        st.write(f"Extraction mode: **{desk.store.mode}** ({desk.store.rejected} figures rejected)")
        st.markdown(md_table([{"Agent": a.section, "Mode": a.mode, "Sentiment": a.sentiment,
                               "Claims": len(a.claims), "Dropped": a.dropped} for a in desk.analyses]))
