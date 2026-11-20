"""Load a report from .txt or .pdf (pypdf is pure Python, so no compiled files)."""
import io
import pathlib
import re


def pdf_to_text(source) -> str:
    """source: a file path or the raw bytes of a PDF."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source))
    pages = [(p.extract_text() or "").strip() for p in reader.pages]
    text = "\n".join(p for p in pages if p)
    if len(text) < 200:
        raise ValueError("No readable text found in this PDF (it may be a scanned image). "
                         "Use a PDF with selectable text, or paste the text into a .txt file.")
    # PDFs break lines mid-sentence: join lines that do not end a sentence
    text = re.sub(r"-\n(?=[a-z])", "", text)
    # join only wrapped lines (long and unfinished); keep titles and page numbers separate
    out = []
    for ln in (x.strip() for x in text.split("\n")):
        if ln and out and len(out[-1]) >= 60 and not re.search(r"[.!?:;]$", out[-1]):
            out[-1] += " " + ln
        else:
            out.append(ln)
    return "\n".join(x for x in out if x)


def load_report(path) -> str:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".pdf":
        return pdf_to_text(p)
    return p.read_text(encoding="utf-8", errors="ignore")
