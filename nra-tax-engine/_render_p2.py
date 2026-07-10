import fitz

doc = fitz.open("assets/templates/2025/f1040nr.pdf")
page = doc[1]
font = fitz.Font("helv")
for w in page.widgets() or []:
    r = w.rect
    name = w.field_name.split(".")[-1]  # f2_16[0]
    tw = fitz.TextWriter(page.rect)
    tw.append((r.x0 + 1, r.y0 + 6), name, font=font, fontsize=6)
    tw.write_text(page, color=(1, 0, 0))
mat = fitz.Matrix(2.4, 2.4)
pix = page.get_pixmap(matrix=mat)
pix.save("_field_maps/f1040nr_p2_labeled.png")
print("saved")
