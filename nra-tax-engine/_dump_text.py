"""Print the static (printed) form text of a page with bounding boxes."""
from __future__ import annotations

import fitz

path = "assets/templates/2025/f1040nr.pdf"
doc = fitz.open(path)
page = doc[0]  # page 1
blocks = page.get_text("dict")["blocks"]
for b in blocks:
    for line in b.get("lines", []):
        for span in line.get("spans", []):
            x0, y0, x1, y1 = span["bbox"]
            txt = span["text"].strip()
            if txt:
                print(f"{x0:7.1f} {y0:7.1f} {x1:7.1f} {y1:7.1f}  {txt!r}")
