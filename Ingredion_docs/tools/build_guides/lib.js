// Small block DSL on top of docx-js for the two Ingredion build guides.
const fs = require("fs");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, LevelFormat, PageBreak, PageNumber,
  Packer, Paragraph, ShadingType, Table, TableCell, TableOfContents, TableRow, TextRun, WidthType, TabStopType,
} = require("docx");

const NAVY = "1B2A4A";
const ACCENT = "2F5BD8";
const MUTED = "5C6774";
const HEAD_FILL = "E3E9F3";
const BAND_FILL = "EEF2F7";
const CODE_FILL = "F3F4F6";
const NOTE_FILL = "FFF7E6";
const CONTENT_W = 9600; // DXA inside A4 with 2 cm margins

// ── dates ────────────────────────────────────────────────────────────────────
const W0 = new Date(Date.UTC(2026, 9, 26)); // Monday 26 October 2026
const DAY = 86400000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function dateOf(week, offsetDays = 0) { return new Date(W0.getTime() + (week * 7 + offsetDays) * DAY); }
function fmt(d, withDay = false) {
  const s = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  return withDay ? `${DAYS[d.getUTCDay()]} ${s}` : s;
}
const mon = (w) => fmt(dateOf(w, 0));
const fri = (w) => fmt(dateOf(w, 4));
const monD = (w) => fmt(dateOf(w, 0), true);
const friD = (w) => fmt(dateOf(w, 4), true);
const span = (w1, w2) => (w1 === w2 ? `week ${w1} (${mon(w1)} to ${fri(w1)})` : `weeks ${w1} to ${w2} (${mon(w1)} to ${fri(w2)})`);
const by = (w) => `by ${friD(w)}`;

// ── block constructors ───────────────────────────────────────────────────────
const H1 = (text) => ({ t: "h1", text });
const H2 = (text) => ({ t: "h2", text });
const H3 = (text) => ({ t: "h3", text });
const P = (text) => ({ t: "p", text });
const UL = (items) => ({ t: "ul", items });
const OL = (items) => ({ t: "ol", items });
const T = (headers, rows, widths) => ({ t: "table", headers, rows, widths });
const CODE = (text) => ({ t: "code", text });
const NOTE = (text) => ({ t: "note", text });
const PB = () => ({ t: "pb" });

// ── inline markup: **bold**, `code` ──────────────────────────────────────────
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: tok.slice(1, -1), font: "Consolas", size: (base.size || 22) - 2, ...base }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

let olInstance = 0;

function cell(text, width, { header = false, band = false } = {}) {
  const paras = String(text).split("\n").map((line) => new Paragraph({
    children: runs(line, { size: 18, bold: header || band, color: header || band ? NAVY : undefined }),
    spacing: { before: 0, after: 0 },
  }));
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { fill: HEAD_FILL, type: ShadingType.CLEAR, color: "auto" } : band ? { fill: BAND_FILL, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: paras,
  });
}

function table(block) {
  const n = block.headers.length;
  const ratios = block.widths || block.headers.map(() => 1);
  const total = ratios.reduce((a, b) => a + b, 0);
  const widths = ratios.map((r) => Math.round((CONTENT_W * r) / total));
  const rows = [
    new TableRow({ tableHeader: true, children: block.headers.map((h, i) => cell(h, widths[i], { header: true })) }),
  ];
  for (const r of block.rows) {
    if (r.band) {
      rows.push(new TableRow({ children: [new TableCell({ columnSpan: n, width: { size: CONTENT_W, type: WidthType.DXA }, shading: { fill: BAND_FILL, type: ShadingType.CLEAR, color: "auto" }, margins: { top: 60, bottom: 60, left: 90, right: 90 }, children: [new Paragraph({ children: runs(r.band, { size: 18, bold: true, color: NAVY }) })] })] }));
      continue;
    }
    rows.push(new TableRow({ children: r.map((c, i) => cell(c, widths[i])) }));
  }
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "CFD6E0" }, bottom: { style: BorderStyle.SINGLE, size: 4, color: "CFD6E0" },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "CFD6E0" }, insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    },
  });
}

function render(block) {
  switch (block.t) {
    case "h1": return [new Paragraph({ children: runs(block.text, { size: 34, bold: true, color: NAVY }), heading: HeadingLevel.HEADING_1 })];
    case "h2": return [new Paragraph({ children: runs(block.text, { size: 27, bold: true, color: NAVY }), heading: HeadingLevel.HEADING_2 })];
    case "h3": return [new Paragraph({ children: runs(block.text, { size: 23, bold: true, color: ACCENT }), heading: HeadingLevel.HEADING_3 })];
    case "p": return [new Paragraph({ children: runs(block.text), spacing: { after: 120 } })];
    case "ul": return block.items.map((it) => new Paragraph({ children: runs(it), numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 } }));
    case "ol": {
      olInstance += 1;
      return block.items.map((it) => new Paragraph({ children: runs(it), numbering: { reference: "numbers", level: 0, instance: olInstance }, spacing: { after: 60 } }));
    }
    case "table": return [table(block), new Paragraph({ spacing: { after: 120 } })];
    case "code": return block.text.split("\n").map((line, i, arr) => new Paragraph({
      children: [new TextRun({ text: line.length ? line : " ", font: "Consolas", size: 17 })],
      shading: { fill: CODE_FILL, type: ShadingType.CLEAR, color: "auto" },
      spacing: { before: 0, after: i === arr.length - 1 ? 160 : 0, line: 260 },
      indent: { left: 200 },
    }));
    case "note": return [new Paragraph({
      children: runs(block.text, { size: 20 }),
      shading: { fill: NOTE_FILL, type: ShadingType.CLEAR, color: "auto" },
      border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 8 } },
      spacing: { before: 80, after: 160 }, indent: { left: 200, right: 200 },
    })];
    case "pb": return [new Paragraph({ children: [new PageBreak()] })];
    default: throw new Error(`unknown block ${block.t}`);
  }
}

function cover(meta) {
  const line = (text, opts) => new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 120 } });
  return [
    new Paragraph({ spacing: { before: 2400 } }),
    line(meta.kicker, { bold: true, color: ACCENT, size: 20 }),
    new Paragraph({ children: [new TextRun({ text: meta.title, bold: true, size: 52, color: NAVY })], spacing: { after: 200 } }),
    line(meta.subtitle, { size: 26, color: MUTED }),
    new Paragraph({ spacing: { before: 1800 } }),
    line(`Prepared by ${meta.author}, ${meta.org}`, { size: 22 }),
    line(`Date ${meta.date}  ·  Version ${meta.version}  ·  Internal working document`, { size: 22 }),
    line(`Basis: ${meta.basis}`, { size: 20, color: MUTED }),
    new Paragraph({ spacing: { before: 1400 } }),
    line("Calendar used throughout: Week 0 is the week of Monday 26 October 2026 (SOW No. 07, section 1.3 and Appendix 1). \"Done by\" dates are the Friday of the last planned week in the WBS of 23 October 2026.", { size: 18, color: MUTED }),
    new Paragraph({ children: [new PageBreak()] }),
    new Paragraph({ text: "Contents", heading: HeadingLevel.HEADING_1 }),
    new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
    new Paragraph({ children: [new TextRun({ text: "If the contents list is empty, right-click it in Word and choose Update Field, or press F9.", size: 18, color: MUTED })] }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

async function buildDoc(meta, blocks, outPath) {
  olInstance = 0;
  const children = [...cover(meta)];
  for (const b of blocks) children.push(...render(b));
  const doc = new Document({
    creator: meta.author,
    lastModifiedBy: meta.author,
    title: meta.title,
    subject: meta.subtitle,
    description: meta.basis,
    keywords: meta.keywords,
    features: { updateFields: process.env.DOCX_NO_UPDATE_FIELDS ? false : true },
    styles: {
      default: { document: { run: { font: "Calibri", size: 22, color: "1B232D" } } },
      paragraphStyles: [
        { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Calibri", size: 22, color: "1B232D" }, paragraph: { spacing: { line: 276 } } },
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 34, bold: true, color: NAVY, font: "Calibri" }, paragraph: { spacing: { before: 420, after: 160 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 27, bold: true, color: NAVY, font: "Calibri" }, paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, color: ACCENT, font: "Calibri" }, paragraph: { spacing: { before: 220, after: 80 }, outlineLevel: 2 } },
      ],
    },
    numbering: {
      config: [
        { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
        { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 320 } } } }] },
      ],
    },
    sections: [{
      properties: { page: { margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 } } },
      headers: { default: new Header({ children: [new Paragraph({ children: [new TextRun({ text: meta.header, size: 17, color: MUTED })], alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CFD6E0", space: 4 } } })] }) },
      footers: { default: new Footer({ children: [new Paragraph({
        tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
        children: [
          new TextRun({ text: `Prepared by ${meta.author}, ${meta.org} · ${meta.date} · Internal`, size: 17, color: MUTED }),
          new TextRun({ text: "\tPage ", size: 17, color: MUTED }),
          new TextRun({ children: [PageNumber.CURRENT], size: 17, color: MUTED }),
          new TextRun({ text: " of ", size: 17, color: MUTED }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 17, color: MUTED }),
        ],
      })] }) },
      children,
    }],
  });
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(outPath, buf);
  return buf.length;
}

module.exports = { H1, H2, H3, P, UL, OL, T, CODE, NOTE, PB, buildDoc, mon, fri, monD, friD, span, by, fmt, dateOf };
