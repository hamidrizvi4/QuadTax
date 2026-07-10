"""For each page, print AcroForm fields with the nearest printed label text.

Helps correlate a positional field (f1_XX) to the form line it represents.
PDF y-axis is bottom-up; we flip to top-down to match printed-text coords.
"""
from __future__ import annotations

import fitz

PAGE_H = 792.0


def collect(path: str, page_no: int):
    doc = fitz.open(path)
    page = doc[page_no - 1]
    # Printed text spans with top-down y.
    texts = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                x0, y0, x1, y1 = span["bbox"]
                t = span["text"].strip()
                if t:
                    texts.append((x0, y0, x1, y1, t))
    return doc, texts


def corr(path, page_no, stem):
    doc, texts = collect(path, page_no)
    page = doc[page_no - 1]
    print(f"\n===== {stem} page {page_no} =====")
    for w in page.widgets() or []:
        r = w.rect
        name = w.field_name
        fx0, fy0, fx1, fy1 = r.x0, r.y0, r.x1, r.y1
        # field center (fitz coords are top-down already)
        cx = (fx0 + fx1) / 2
        cy = (fy0 + fy1) / 2
        # find printed text whose center is near the field center
        near = []
        for (tx0, ty0, tx1, ty1, t) in texts:
            tcx = (tx0 + tx1) / 2
            tcy = (ty0 + ty1) / 2
            if abs(tcx - cx) < 70 and abs(tcy - cy) < 40:
                near.append((round(tcy - cy, 1), t))
        near.sort()
        label = " | ".join(t for _, t in near[:4])
        print(f"{name:14} x[{fx0:6.1f},{fx1:6.1f}] y[{fy0:6.1f},{fy1:6.1f}]  ~ {label}")
    doc.close()


corr("assets/templates/2025/f1040nr.pdf", 2, "f1040nr")
