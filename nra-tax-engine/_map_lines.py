"""For a set of target line-label tokens, find the AcroForm field box that
sits immediately to the RIGHT of the token (the dollar-amount entry box)."""
from __future__ import annotations

import fitz

TARGETS = [
    "11b", "12", "13a", "13b", "13c", "14", "15", "16", "17", "18",
    "19", "20", "21", "22", "23a", "23b", "23c", "23d", "24", "25",
    "25a", "25b", "25c", "25d", "25e", "25f", "25g", "26", "27", "28",
    "29", "30", "31", "32", "33", "34", "35a", "36", "37", "38",
    # page 1 lines
    "1a", "1k", "1z", "8", "9", "11a",
]


def map_page(path, page_no, stem):
    doc = fitz.open(path)
    page = doc[page_no - 1]
    fields = []
    for w in page.widgets() or []:
        r = w.rect
        fields.append((r.x0, r.y0, r.x1, r.y1, w.field_name))
    # token spans
    toks = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                x0, y0, x1, y1 = s["bbox"]
                t = s["text"].strip()
                if t:
                    toks.append((x0, y0, x1, y1, t))
    print(f"\n===== {stem} page {page_no} =====")
    for tgt in TARGETS:
        # find token exactly equal to tgt
        for (tx0, ty0, tx1, ty1, t) in toks:
            if t == tgt:
                tcx = (tx0 + tx1) / 2
                tcy = (ty0 + ty1) / 2
                # amount box center depends on which column the line number is in
                box_cx = 445.0 if tx0 < 300 else 540.0
                best = None
                best_dist = 1e9
                for (fx0, fy0, fx1, fy1, fn) in fields:
                    fcx = (fx0 + fx1) / 2
                    fcy = (fy0 + fy1) / 2
                    if abs(fcy - tcy) < 14 and 380 < fcx < 590:
                        d = abs(fcx - box_cx) + abs(fcy - tcy) * 2
                        if d < best_dist:
                            best_dist = d
                            best = (fn, round(fx0, 1), round(fy0, 1))
                if best:
                    print(f"{tgt:5} -> {best[0]:14} x0={best[1]} y0={best[2]}")
                else:
                    print(f"{tgt:5} -> (no field found)")
                break


map_page("assets/templates/2025/f1040nr.pdf", 2, "f1040nr")
map_page("assets/templates/2025/f1040nr.pdf", 1, "f1040nr")
