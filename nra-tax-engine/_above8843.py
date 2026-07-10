import fitz

doc = fitz.open("assets/templates/2025/f8843.pdf")
for pno in (0, 1):
    page = doc[pno]
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                t = s["text"].strip()
                if t:
                    spans.append((s["bbox"], t))
    print(f"\n===== page {pno+1} =====")
    for w in sorted(page.widgets() or [], key=lambda w: (round(w.rect.y0, 1), round(w.rect.x0, 1))):
        r = w.rect
        cx = (r.x0 + r.x1) / 2
        above = []
        for (tx0, ty0, tx1, ty1), t in spans:
            if ty1 <= r.y0 + 1 and (tx0 + tx1) / 2 > r.x0 - 30 and (tx0 + tx1) / 2 < r.x1 + 30:
                above.append((r.y0 - ty1, t))
        above.sort()
        lbl = " / ".join(t for _, t in above[:3]) if above else "<none>"
        print(f"{w.field_name:46} ~ {lbl}")
