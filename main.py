import asyncio
import pathlib
import sys

from desk.editor_manager import EditorManager
from desk.reader import load_report

path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_report.txt"   # .txt or .pdf
report = load_report(path)
print(f"Loaded {path}: {len(report):,} characters")
note = asyncio.run(EditorManager().run(report))
pathlib.Path("analyst_note.md").write_text(note, encoding="utf-8")
print(note)