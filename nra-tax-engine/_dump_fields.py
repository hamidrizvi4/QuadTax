from pypdf import PdfReader
import os

stems = ['f1040nr', 'f1040nro', 'f1040nra', 'f1040nrn', 'f8843', 'f8833',
         'f843', 'fw7', 'f6251', 'f2210', 'f8316']
for s in stems:
    p = f'assets/templates/2025/{s}.pdf'
    if not os.path.exists(p):
        print(f'--- {s}: MISSING ---')
        continue
    try:
        r = PdfReader(p)
        fields = r.get_fields()
        names = sorted(fields.keys()) if fields else []
        print(f'--- {s}: {len(names)} fields ---')
        for n in names[:300]:
            print('   ', n)
    except Exception as e:
        print(f'--- {s}: ERROR {e} ---')
