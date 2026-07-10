import fitz

doc = fitz.open("assets/templates/2025/f8843.pdf")
page = doc[0]
print("PAGE1 geometry (x0,y0,w,h) in PDF points:")
for w in sorted(page.widgets() or [], key=lambda w: (round(w.rect.y0, 1), round(w.rect.x0, 1))):
    r = w.rect
    print(
        f"{w.field_name:46} x0={r.x0:6.1f} y0={r.y0:6.1f} w={r.width:5.1f} "
        f"h={r.height:4.1f} ft={w.field_type_string}"
    )
