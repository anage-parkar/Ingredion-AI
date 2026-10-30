"""Render selected PDF pages to PNG for a visual check: render_pages.py file.pdf out_prefix 1 2 5"""

import sys
from pathlib import Path

import pypdfium2 as pdfium

pdf = pdfium.PdfDocument(sys.argv[1])
prefix = sys.argv[2]
pages = [int(p) for p in sys.argv[3:]] or list(range(1, len(pdf) + 1))
for n in pages:
    page = pdf[n - 1]
    image = page.render(scale=1.35).to_pil()
    out = Path(f"{prefix}-p{n:02d}.png")
    image.save(out)
    print(out, image.size)
