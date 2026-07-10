"""Dump every AcroForm field of a template with its nearest printed labels.

Usage: .venv/bin/python _field_report.py <stem>   (e.g. f1040nr)

Emits, per page, one line per widget:
    <field_name>  col=<L|R|?>  y=<top>  ~ <up to 5 nearest printed spans>

The nearest-label text plus the column (amount boxes sit at x-center ~445 for
the left/inner column, ~540 for the right/outer column) is enough to correlate
a populator's human key to the real field. Read-order subforms keep their full
dotted path so the name is copy-pasteable into <stem>_fields.json.
"""
from __future__ import annotations

import sys

import fitz


def report(stem: str) -> None:
    path = f"assets/templates/2025/{stem}.pdf"
    doc = fitz.open(path)
    for pno, page in enumerate(doc, start=1):
        spans = []
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    t = s["text"].strip()
                    if t:
                        spans.append((*s["bbox"], t))
        print(f"\n===== {stem} page {pno} =====")
        widgets = sorted(page.widgets() or [], key=lambda w: (round(w.rect.y0), w.rect.x0))
        for w in widgets:
            r = w.rect
            cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
            col = "L" if 380 < cx < 490 else "R" if cx >= 490 else "?"
            near = sorted(
                (
                    (round(((tx0 + tx1) / 2 - cx) ** 2 + ((ty0 + ty1) / 2 - cy) ** 2, 1), t)
                    for tx0, ty0, tx1, ty1, t in spans
                    if abs((ty0 + ty1) / 2 - cy) < 22 and abs((tx0 + tx1) / 2 - cx) < 120
                ),
            )[:5]
            labels = " | ".join(t for _, t in near)
            print(f"{w.field_name:52} col={col} y={r.y0:6.1f}  ~ {labels}")
    doc.close()


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else "f1040nr")
