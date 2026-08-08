"""Throwaway: dump the fresh issue and the QA findings."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

con = sqlite3.connect("_fly.db")
con.row_factory = sqlite3.Row
row = con.execute(
    "select week, subject_line, preheader, html_content, text_content, slots, tldr "
    "from newsletters order by created_at desc limit 1",
).fetchone()
Path("preview.html").write_text(row["html_content"] or "", encoding="utf-8")
Path("preview.txt").write_text(row["text_content"] or "", encoding="utf-8")

out = [
    row["week"],
    f"subject:   {row['subject_line']}",
    f"preheader: {row['preheader']}",
    "",
    "TLDR:",
]
out.extend(f"  - {line}" for line in json.loads(row["tldr"] or "[]"))
out.append("")

for slot in json.loads(row["slots"]):
    ed = slot.get("editorial", {})
    out.append(f"[{slot.get('section')}]  kind={ed.get('implication_kind')}")
    out.append(f"  titolo:  {ed.get('headline_operational', '')}")
    out.append(f"  fonte:   {slot.get('source_name')}")
    out.append(f"  perche:  {ed.get('why_it_matters', '')[:220]}")
    actions = ed.get("what_to_do", [])
    out.append(f"  azione:  {actions[0][:180] if actions else '(NESSUNA)'}")
    out.append(f"  nota:    {ed.get('source_note', '')[:150]}")
    out.append("")

Path("_report.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
