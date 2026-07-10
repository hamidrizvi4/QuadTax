"""Render each IRS template page with its AcroForm field names overlaid.

Produces PNGs under _field_maps/ so the field positions can be visually
correlated to the printed form lines. Run: .venv/bin/python _render_fields.py
"""
from __future__ import annotations

import os

import fitz  # PyMuPDF

STEMS = {
    "f1040nr": "assets/templates/2025/f1040nr.pdf",
    "f1040nro": "assets/templates/2025/f1040nro.pdf",
    "f1040nra": "assets/templates/2025/f1040nra.pdf",
    "f1040nrn": "assets/templates/2025/f1040nrn.pdf",
    "f8843": "assets/templates/2025/f8843.pdf",
    "f8833": "assets/templates/2025/f8833.pdf",
    "f843": "assets/templates/2025/f843.pdf",
    "fw7": "assets/templates/2025/fw7.pdf",
    "f6251": "assets/templates/2025/f6251.pdf",
    "f2210": "assets/templates/2025/f2210.pdf",
    "f8316": "assets/templates/2025/f8316.pdf",
}

OUT = "_field_maps"
os.makedirs(OUT, exist_ok=True)


def render(pdf_path: str, stem: str) -> None:
    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc, start=1):
        font = fitz.Font("helv")
        for w in page.widgets() or []:
            rect = w.rect
            field = w.field_name
            tw = fitz.TextWriter(page.rect)
            tw.append(
                (rect.x0 + 1, rect.y0 + 5),
                field,
                font=font,
                fontsize=5,
            )
            tw.write_text(page, color=(1, 0, 0))
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        out = os.path.join(OUT, f"{stem}_p{page_idx}.png")
        pix.save(out)
        print("wrote", out)
    doc.close()


for stem, path in STEMS.items():
    if os.path.exists(path):
        render(path, stem)
