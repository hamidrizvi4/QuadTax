from pypdf import PdfReader
import os

stem = "f1040nr"
p = f"assets/templates/2025/{stem}.pdf"
r = PdfReader(p)

# Walk the AcroForm field tree, capturing name, tooltip (/TU), value (/V),
# and widget rectangle so we can map positional fields to form lines.
root = r.root_object["/AcroForm"]
fields = root.get("/Fields", [])


def walk(field_ref, depth=0):
    obj = field_ref.get_object()
    name = obj.get("/T")
    tu = obj.get("/TU")
    ft = obj.get("/FT")
    rect = obj.get("/Rect")
    # Try to get tooltip if this is a widget with /TU
    if name is not None or tu is not None:
        nm = str(name) if name is not None else ""
        tt = str(tu) if tu is not None else ""
        if tt or nm:
            print(f"{nm!r:40} tu={tt!r:50} rect={rect}")
    kids = obj.get("/Kids")
    if kids:
        for k in kids:
            walk(k, depth + 1)


for f in fields:
    walk(f)
