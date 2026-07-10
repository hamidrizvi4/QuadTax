import fitz

doc = fitz.open("assets/templates/2025/f8843.pdf")
for pno in (0, 1):
    page = doc[pno]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    out = f"/tmp/f8843_p{pno+1}.png"
    pix.save(out)
    print(out)
