"""Build the Ingredion Agent Workflows PDF from the HTML page.

Pass 1 prints with Chrome to learn which page each section lands on (from the
named destinations Chrome writes for anchors), pass 2 prints again with page
numbers in the contents, then pypdf adds bookmarks and metadata and a reportlab
overlay stamps the running footer. Figures go on landscape pages so the vector
diagrams stay legible.
"""

from __future__ import annotations

import html as html_mod
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

SRC = Path(sys.argv[1])
WORK = Path(sys.argv[2])
FINAL = Path(sys.argv[3])
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

AUTHOR = "Abhishek Nage"
ORG = "Parkar"
TITLE = "Ingredion Agent Workflows"
DATE = "21 October 2026"

pdfmetrics.registerFont(TTFont("Calibri", r"C:\Windows\Fonts\calibri.ttf"))

PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
@page wide { size: A4 landscape; margin: 9mm 10mm 16mm 10mm; }
html { background: #fff; }
body { background: #fff; color: #1B232D; font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; margin: 0; }
.wrap { max-width: none; margin: 0; padding: 0; }
h2 { font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size: 17pt; margin: 18px 0 6px; break-after: avoid; color: #1B2A4A; }
h2 .uc { font-size: 8.5pt; }
h3 { font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size: 12.5pt; margin: 14px 0 5px; break-after: avoid; color: #1B2A4A; }
p { max-width: none; }
.sub { margin-top: -2px; }
.verdict { break-inside: auto; }
.verdict .pill { break-inside: avoid; }
table { font-size: 8.8pt; break-inside: auto; }
th, td { padding: 4px 5px; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
.tbl { overflow: visible; }
.tbl table { min-width: 0; }
.two { grid-template-columns: 1fr; gap: 10px; }
pre { font-size: 8pt; white-space: pre-wrap; break-inside: avoid; }
figure.landscape { page: wide; break-before: page; break-after: page; margin: 0; }
figure.landscape .scroll { overflow: visible; border: none; border-radius: 0; break-inside: avoid; text-align: center; }
figure.landscape .dg { display: inline-block; width: 100% !important; max-width: 100%; height: auto; max-height: 168mm; }
figure.landscape figcaption { max-width: none; margin-top: 4px; font-size: 8.5pt; line-height: 1.35; }
.legend { font-size: 8.5pt; }
footer { font-size: 8.5pt; }
.dg text { font-family: Calibri, "Segoe UI", Arial, sans-serif; }

/* cover */
.cover { height: 240mm; display: flex; flex-direction: column; justify-content: flex-start; break-after: page; }
.cover .kicker { color: #2F5BD8; font-weight: 700; font-size: 9.5pt; letter-spacing: .08em; text-transform: uppercase; margin: 46mm 0 6px; }
.cover h1 { font-size: 30pt; line-height: 1.1; margin: 0 0 10px; color: #1B2A4A; font-family: Calibri, "Segoe UI", Arial, sans-serif; }
.cover .lede { font-size: 12.5pt; color: #5C6774; max-width: 150mm; margin: 0 0 26mm; }
.cover .meta p { margin: 2px 0; }
.cover .basis { margin-top: 24mm; font-size: 9.5pt; color: #5C6774; max-width: 150mm; }
.cover .rule { border-top: 3px solid #2F5BD8; width: 42mm; margin: 0 0 14px; }

/* contents */
.toc { break-after: page; }
.toc ol { list-style: none; padding: 0; margin: 10px 0 0; }
.toc li a { display: flex; justify-content: space-between; align-items: baseline; text-decoration: none; color: #1B232D; padding: 5px 0; border-bottom: 1px solid #E3E9F3; }
.toc li.l2 a { padding-left: 18px; color: #5C6774; font-size: 9.5pt; }
.toc li a .p { color: #5C6774; font-variant-numeric: tabular-nums; }
"""


def strip_tags(s: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ").strip()


def prepare_html(src: str, page_numbers: dict[str, int] | None) -> tuple[str, list[tuple[int, str, str]]]:
    style = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    style = re.sub(r"@media \(prefers-color-scheme: dark\)\s*\{.*?\n  \}\n", "", style, flags=re.S)
    style = re.sub(r":root\[data-theme=\"dark\"\]\s*\{.*?\n  \}\n", "", style, flags=re.S)
    body = re.search(r'<div class="wrap">(.*)</div>\s*$', src, re.S).group(1)
    # the artifact header becomes the cover; its lede is reused there
    header = re.search(r"<header>(.*?)</header>", body, re.S)
    lede = strip_tags(re.search(r'<p class="lede">(.*?)</p>', header.group(1), re.S).group(1)) if header else ""
    body = body.replace(header.group(0), "", 1) if header else body
    body = body.replace('<span class="pill amber">Updated 19 Oct</span>', '<span class="pill amber">Revision of 19 Oct</span>')
    body = body.replace("The AVP discussion and the three new documents confirm", "The AVP discussion and the three new Order Intake documents confirm")

    # section ids and the contents list
    entries: list[tuple[int, str, str]] = []
    counter = {"n": 0}

    def add_id(match: re.Match) -> str:
        tag, attrs, inner = match.group(1), match.group(2), match.group(3)
        counter["n"] += 1
        sid = f"sec-{counter['n']}"
        level = 1 if tag == "h2" else 2
        label = re.sub(r"\s+", " ", strip_tags(inner.replace("</span>", "</span> · ")))
        entries.append((level, sid, label))
        return f'<{tag} id="{sid}"{attrs}>{inner}</{tag}>'

    body = re.sub(r"<(h2|h3)([^>]*)>(.*?)</\1>", add_id, body, flags=re.S)
    body = body.replace("<figure>", '<figure class="landscape">')

    toc_items = []
    for level, sid, text in entries:
        page = page_numbers.get(sid, "") if page_numbers else ""
        toc_items.append(f'<li class="l{level}"><a href="#{sid}"><span class="t">{html_mod.escape(text)}</span><span class="p">{page}</span></a></li>')
    cover = f"""
<section class="cover">
  <div class="kicker">Ingredion Agentic AI Factory</div>
  <h1>{TITLE}</h1>
  <div class="rule"></div>
  <p class="lede">Agent A, the Email Order Intake Agent as primary processor for every email-order case, and Agent B, the Pre-bill Validation and Dispute Prevention Agent, both on Google Cloud per Ingredion's redline v2: the step-by-step flows, the shared runtime they run on, and the engineering review of what remains to settle before Gate 2.</p>
  <div class="meta">
    <p><b>Prepared by</b> {AUTHOR}, {ORG}</p>
    <p><b>Date</b> {DATE} &nbsp;·&nbsp; <b>Version</b> 1.1 &nbsp;·&nbsp; <b>Status</b> for internal review</p>
  </div>
  <p class="basis"><b>Basis.</b> {html_mod.escape(lede)}</p>
</section>
<nav class="toc"><h2>Contents</h2><ol>{''.join(toc_items)}</ol></nav>
"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>
<style>{style}</style><style>{PRINT_CSS}</style></head><body><div class="wrap">{cover}{body}</div></body></html>"""
    return doc, entries


def chrome_print(html_path: Path, pdf_path: Path) -> None:
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
        "--virtual-time-budget=8000", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=False, capture_output=True, timeout=180)
    if not pdf_path.exists():
        raise SystemExit("Chrome did not produce a PDF")


def destination_pages(pdf_path: Path) -> dict[str, int]:
    reader = PdfReader(str(pdf_path))
    out: dict[str, int] = {}
    for name, dest in reader.named_destinations.items():
        try:
            out[name.lstrip("/")] = reader.get_destination_page_number(dest) + 1
        except Exception:
            continue
    return out


def footer_overlay(width: float, height: float, page_no: int, total: int) -> PdfReader:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    margin = 16 * 72 / 25.4 if width < height else 12 * 72 / 25.4
    y = 9.5 * 72 / 25.4
    c.setStrokeColor(colors.HexColor("#CFD6E0"))
    c.setLineWidth(0.6)
    c.line(margin, y + 11, width - margin, y + 11)
    c.setFont("Calibri", 8.5)
    c.setFillColor(colors.HexColor("#5C6774"))
    c.drawString(margin, y, f"{TITLE} · {ORG} internal · prepared by {AUTHOR}")
    c.drawRightString(width - margin, y, f"Page {page_no} of {total}")
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def finalise(pdf_path: Path, entries: list[tuple[int, str, str]], pages: dict[str, int]) -> None:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    total = len(reader.pages)
    for i, page in enumerate(reader.pages):
        if i > 0:
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            page.merge_page(footer_overlay(w, h, i + 1, total).pages[0])
        writer.add_page(page)
    # bookmarks: cover, contents, then each section (h3 nested under its h2)
    writer.add_outline_item("Cover", 0)
    writer.add_outline_item("Contents", 1)
    parent = None
    for level, sid, text in entries:
        if sid not in pages:
            continue
        if level == 1:
            parent = writer.add_outline_item(text, pages[sid] - 1)
        else:
            writer.add_outline_item(text, pages[sid] - 1, parent=parent)
    writer.add_metadata(
        {
            "/Title": TITLE,
            "/Author": AUTHOR,
            "/Subject": "Email Order Intake and Pre-bill Validation agents: workflows, shared runtime, engineering review",
            "/Creator": f"{AUTHOR}, {ORG}",
            "/Producer": ORG,
            "/Keywords": "Ingredion, Agentic AI Factory, Email Order Intake, Pre-bill Validation, SOW",
        }
    )
    writer.page_mode = "/UseOutlines"
    FINAL.parent.mkdir(parents=True, exist_ok=True)
    with FINAL.open("wb") as fh:
        writer.write(fh)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    src = SRC.read_text(encoding="utf-8")
    for word in re.findall(r"\b(you|your|yours)\b", strip_tags(src), flags=re.I):
        print("second person found:", word)
    html1, entries = prepare_html(src, None)
    (WORK / "workflow-pass1.html").write_text(html1, encoding="utf-8")
    chrome_print(WORK / "workflow-pass1.html", WORK / "workflow-pass1.pdf")
    pages = destination_pages(WORK / "workflow-pass1.pdf")
    missing = [sid for _, sid, _ in entries if sid not in pages]
    print("sections:", len(entries), "resolved pages:", len(pages), "missing:", missing)
    html2, _ = prepare_html(src, pages)
    (WORK / "workflow-pass2.html").write_text(html2, encoding="utf-8")
    chrome_print(WORK / "workflow-pass2.html", WORK / "workflow-pass2.pdf")
    pages2 = destination_pages(WORK / "workflow-pass2.pdf")
    if pages2 != pages:
        print("page numbers moved between passes; using pass-2 numbers for bookmarks")
    finalise(WORK / "workflow-pass2.pdf", entries, pages2)
    print("written", FINAL, "pages", len(PdfReader(str(FINAL)).pages))


if __name__ == "__main__":
    main()
