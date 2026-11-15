import asyncio
import pathlib
import sys

from desk.editor_manager import EditorManager

path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_report.txt"
report = pathlib.Path(path).read_text(encoding="utf-8")
note = asyncio.run(EditorManager().run(report))
pathlib.Path("analyst_note.md").write_text(note, encoding="utf-8")
print(note)
