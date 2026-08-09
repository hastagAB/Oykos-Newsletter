"""Throwaway: print the composed issue the way a reader meets it."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

con = sqlite3.connect("_fly.db")
con.row_factory = sqlite3.Row
row = con.execute(
    "select subject_line, preheader, tldr, slots from newsletters "
    "where week='2026-W32' order by created_at desc limit 1",
).fetchone()

out = [
    f"OGGETTO:   {row['subject_line']}",
    f"ANTEPRIMA: {row['preheader']}",
    "",
    "CHE COSA MERITA ATTENZIONE QUESTA SETTIMANA",
]
out += [f"  - {line}" for line in json.loads(row["tldr"] or "[]")]

for slot in json.loads(row["slots"]):
    ed = slot["editorial"]
    out += [
        "",
        "-" * 72,
        f"{ed['headline_operational']}",
        "",
        f"COSA EMERGE:   {ed.get('what_emerges', '(VUOTO)')}",
        f"PERCHE' PLS:   {ed['why_it_matters']}",
    ]
    for action in ed["what_to_do"]:
        out.append(f"IMPLICAZIONE:  {action}")
    if not ed["what_to_do"]:
        out.append("IMPLICAZIONE:  (nessuna)")
    out.append(f"FONTE/LIMITI:  {ed['source_note']}")

Path("_issue.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
