// Kick-off deck for Ingredion SOW No. 07, in the visual language of the Parkar reference deck.
const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = process.argv[2] || "Ingredion_Agentic_AI_Factory_Project_Kickoff.pptx";
const MEDIA = path.join(__dirname, "media");
const LOGO = path.join(MEDIA, "image1.png");       // Parkar logo (515x350)
const INGREDION = path.join(MEDIA, "image3.png");  // Ingredion logo (402x220)
const HERO = path.join(MEDIA, "hero.png");         // cover artwork

const C = { title: "1F4D2B", green: "4C8B2B", text: "2E3A2F", grey: "6B7A6E", cardA: "EEF6E3", cardB: "F7FBF1", border: "D3E4BE", white: "FFFFFF", soft: "F2F8EA" };
const FT = "Cambria";
const FB = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Abhishek Nage";
pres.company = "Parkar";
pres.title = "Ingredion Agentic AI Factory - Project Kick-off";
pres.subject = "SOW No. 07: Email Order Intake Agent and Pre-bill Validation Agent";

let pageNo = 0;

function chrome(slide, { title, subtitle } = {}) {
  pageNo += 1;
  slide.background = { color: C.white };
  if (title) {
    slide.addText(title, { x: 0.6, y: 0.38, w: 10.4, h: 0.55, fontFace: FT, fontSize: 30, bold: true, color: C.title, valign: "middle", margin: 0, isTextBox: true });
  }
  if (subtitle) {
    slide.addText(subtitle, { x: 0.6, y: 0.95, w: 10.4, h: 0.3, fontFace: FB, fontSize: 11, italic: true, color: C.grey, valign: "middle", margin: 0, isTextBox: true });
  }
  slide.addImage({ path: LOGO, x: 11.38, y: 0.34, w: 1.35, h: 0.92 });
  slide.addText("Parkar Internal Confidential", { x: 0.6, y: 7.02, w: 5.0, h: 0.28, fontFace: FB, fontSize: 8, color: C.grey, margin: 0, isTextBox: true });
  slide.addText(String(pageNo), { x: 11.73, y: 7.02, w: 1.0, h: 0.28, fontFace: FB, fontSize: 8, color: C.grey, align: "right", margin: 0, isTextBox: true });
}

function card(slide, x, y, w, h, fill = C.cardA) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: C.border, width: 1 }, rectRadius: 0.08 });
}

function circle(slide, x, y, d, label, fontSize = 14) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: C.green }, line: { color: C.green, width: 1 } });
  slide.addText(label, { x, y, w: d, h: d, fontFace: FB, fontSize, bold: true, color: C.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
}

function label(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, { x, y, w, h, fontFace: FB, fontSize: 13, color: C.text, margin: 0, isTextBox: true, valign: "top", ...opts });
}

function bullets(slide, items, x, y, w, h, opts = {}) {
  const runs = items.map((t, i) => ({ text: t, options: { bullet: { indent: 12 }, breakLine: i < items.length - 1 } }));
  slide.addText(runs, { x, y, w, h, fontFace: FB, fontSize: 13, color: C.text, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 4, ...opts });
}

function table(slide, header, rows, { x = 0.6, y = 1.55, w = 12.13, colW, fontSize = 12, headerSize = 13, rowH, bandRows = [] } = {}) {
  const head = header.map((h) => ({ text: h, options: { bold: true, color: C.white, fill: { color: C.green }, fontSize: headerSize, fontFace: FB, valign: "middle" } }));
  const body = rows.map((r, i) => {
    if (r.band) {
      return [{ text: r.band, options: { bold: true, color: C.title, fill: { color: C.cardA }, fontSize, fontFace: FB, colspan: header.length } }];
    }
    const fill = i % 2 === 0 ? C.white : C.cardB;
    return r.map((cell, j) => {
      const isObj = typeof cell === "object" && cell !== null;
      const text = isObj ? cell.text : cell;
      const o = { color: C.text, fill: { color: fill }, fontSize, fontFace: FB, valign: "middle" };
      if (isObj && cell.bold) o.bold = true;
      if (isObj && cell.color) o.color = cell.color;
      if (bandRows.length && j === 0) o.bold = true;
      return { text, options: o };
    });
  });
  slide.addTable([head, ...body], { x, y, w, colW, border: { type: "solid", pt: 0.75, color: C.border }, margin: 0.06, rowH, autoPage: false });
}

// ────────────────────────────────────────────────────────────────────────────
// 1. Cover
{
  const s = pres.addSlide();
  pageNo += 1;
  s.background = { color: C.white };
  s.addImage({ path: LOGO, x: 0.01, y: 0.07, w: 2.87, h: 1.99 });
  s.addImage({ path: HERO, x: 5.82, y: 0.51, w: 7.05, h: 6.19 });
  // Ingredion logo last: the hero artwork has an opaque white background and must sit under it (same z-order as the reference deck).
  s.addImage({ path: INGREDION, x: 10.62, y: 0.04, w: 2.69, h: 1.47 });
  s.addText("Ingredion Agentic AI Factory", { x: 0.85, y: 2.95, w: 6.3, h: 1.0, fontFace: FT, fontSize: 34, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "bottom" });
  s.addText("Email Order Intake Agent  |  Pre-bill Validation Agent", { x: 0.85, y: 4.05, w: 6.3, h: 0.4, fontFace: FB, fontSize: 16, color: C.text, margin: 0, isTextBox: true });
  s.addText("Project Kick-off  ·  Statement of Work No. 07  ·  26 October 2026", { x: 0.85, y: 4.5, w: 6.3, h: 0.4, fontFace: FB, fontSize: 14, color: C.green, margin: 0, isTextBox: true });
  s.addText("INC 5000 Company   ·   Awarded by The CEO Views as a Top Innovative Company", { x: 0.85, y: 6.55, w: 6.4, h: 0.3, fontFace: FB, fontSize: 9, color: C.grey, margin: 0, isTextBox: true });
  s.addNotes("Welcome and purpose of the session: align on scope, plan, prerequisites and owners for SOW No. 07. Both agents start this week (Week 0 is the week of 26 October 2026).");
}

// 2. Agenda
{
  const s = pres.addSlide();
  chrome(s, { title: "Agenda" });
  const items = [
    ["Introductions", "Project organisation structure: Ingredion and Parkar teams"],
    ["Project Overview", "SOW No. 07: two agents, one factory on Google Cloud"],
    ["Key Differentiators", "What changes against the RPA and today's pre-bill handling"],
    ["Timelines & Deliverables", "Six stages, gates and calendar dates for both agents"],
    ["Team Roles & Responsibilities", "Staffing plan, allocations and the RACI in brief"],
    ["Risks, Dependencies & Mitigation", "Week-0 prerequisites and what moves the Stage 1 clock"],
    ["Communication & Governance", "Cadence, reporting, escalation and change control"],
    ["Next Steps & Appendix", "Actions for this week; scorecards and reference documents"],
  ];
  items.forEach(([t, d], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.6 + col * 6.16, y = 1.5 + row * 1.16;
    card(s, x, y, 5.95, 0.98, col === 0 ? C.cardA : C.cardB);
    circle(s, x + 0.24, y + 0.28, 0.42, String(i + 1).padStart(2, "0"), 12);
    s.addText(t, { x: x + 0.82, y: y + 0.17, w: 4.95, h: 0.32, fontFace: FB, fontSize: 20, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(d, { x: x + 0.82, y: y + 0.5, w: 4.95, h: 0.3, fontFace: FB, fontSize: 14, color: C.grey, margin: 0, isTextBox: true, valign: "middle" });
  });
  s.addNotes("Walk through the agenda. Sections 06 and 08 are the action-heavy parts: the prerequisites decide whether the Stage 1 clock starts this week.");
}

// 3. Introductions
{
  const s = pres.addSlide();
  chrome(s, { title: "Introductions: Project Organisation Structure" });
  card(s, 0.6, 1.5, 3.5, 5.3, C.cardA);
  s.addText("INGREDION", { x: 0.88, y: 1.72, w: 3.0, h: 0.32, fontFace: FB, fontSize: 20, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 2 });
  const ing = [
    [{ text: "Executive sponsor  ", options: { bold: true } }, { text: "Matt Levin", options: {} }],
    [{ text: "Technical lead  ", options: { bold: true } }, { text: "Sridevi Matam", options: {} }],
    [{ text: "AI director  ", options: { bold: true } }, { text: "Brian Chau", options: {} }],
    [{ text: "Use-case lead, Order Intake  ", options: { bold: true } }, { text: "to be confirmed", options: {} }],
    [{ text: "Use-case lead, Pre-bill  ", options: { bold: true } }, { text: "Soochul Kim", options: {} }],
    [{ text: "Project Manager  ", options: { bold: true } }, { text: "to be named before signature", options: {} }],
    [{ text: "SMEs  ", options: { bold: true } }, { text: "SAP, Salesforce, Existing RPA, Pricing & Billing, AR & Collections, Customer Service, infrastructure, security", options: {} }],
    [{ text: "Third parties  ", options: { bold: true } }, { text: "Accenture, NTT Data, Infosys (managed by Ingredion); AMS partner for handover", options: {} }],
  ];
  const ingRuns = [];
  ing.forEach((line, i) => { line.forEach((r, j) => ingRuns.push({ text: r.text, options: { ...r.options, bullet: j === 0 ? { indent: 10 } : undefined, breakLine: j === line.length - 1 && i < ing.length - 1 } })); });
  s.addText(ingRuns, { x: 0.8, y: 2.15, w: 3.1, h: 3.5, fontFace: FB, fontSize: 12, color: C.text, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 5 });
  s.addText("Names and availability to be confirmed during kick-off, together with the escalation matrix and the governance cadence.", { x: 0.88, y: 5.75, w: 2.95, h: 0.9, fontFace: FB, fontSize: 10.5, italic: true, color: C.grey, margin: 0, isTextBox: true });

  s.addText("PARKAR DELIVERY TEAM", { x: 4.5, y: 1.5, w: 8.2, h: 0.32, fontFace: FB, fontSize: 20, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 2 });
  const team = [
    ["Hardik Desai", "Engagement lead · AVP Cloud AI", "Escalation level 1"],
    ["Dnyaneshwar N. Bairagi", "Technical Lead / TPM (offshore)", "50% across both agents"],
    ["Niti Bhargava", "Business Analyst (onsite)", "20 hours per week"],
    ["Shanmukhi Neelam", "Forward Deployed Engineer (onsite)", "40 hours per week"],
    ["Ananya Mehta", "AI Engineer · Agent A", "Full time"],
    ["Anshika Ranjan", "AI Engineer · Agent A", "Full time"],
    ["Isha Chandravanshi", "AI / Data Engineer · Agent B", "Full time"],
    ["Abhishek Nage", "AI Engineer · Agent B", "Full time"],
    ["Eshita Khare", "Data / AI Engineer · both agents", "50% per agent"],
    ["Sanjana Sulakhe", "QA Engineer · both agents", "50% per agent"],
    ["SAP S&D SME", "To be named (offshore)", "20 hours per week"],
    ["Amit Gandhi", "CTO · governance", "Escalation level 2"],
  ];
  team.forEach(([n, r, a], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 4.5 + col * 2.83, y = 1.98 + row * 1.2;
    card(s, x, y, 2.6, 1.06, C.white);
    s.addText(n, { x: x + 0.16, y: y + 0.1, w: 2.3, h: 0.3, fontFace: FB, fontSize: 16, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(r, { x: x + 0.16, y: y + 0.42, w: 2.3, h: 0.3, fontFace: FB, fontSize: 11, color: C.green, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(a, { x: x + 0.16, y: y + 0.72, w: 2.3, h: 0.26, fontFace: FB, fontSize: 10.5, color: C.grey, margin: 0, isTextBox: true, valign: "middle" });
  });
  s.addNotes("Quick round of introductions. Confirm the Ingredion use-case lead for Order Intake, the Project Manager and the SMEs for both agents. Parkar allocations are from the staffing plan (Appendix 3); the SAP S&D SME is still to be named.");
}

// 4. Project overview
{
  const s = pres.addSlide();
  chrome(s, { title: "Project Overview: SOW No. 07", subtitle: "Two agents under the Ingredion Agentic AI Factory, delivered in parallel on one platform pattern in the Ingredion GCP environment" });
  const stats = [["2 agents", "One SOW, one factory, two fixed fees"], ["26 Oct 2026", "Week 0 for both agents"], ["18 + 16 weeks", "To production acceptance (Gate 5)"], ["4 weeks", "Hyper care and handover per agent"]];
  stats.forEach(([a, b], i) => {
    const x = 0.6 + i * 3.09;
    card(s, x, 1.42, 2.94, 1.0, C.cardA);
    s.addText(a, { x: x + 0.2, y: 1.52, w: 2.6, h: 0.45, fontFace: FT, fontSize: 21, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(b, { x: x + 0.2, y: 1.97, w: 2.6, h: 0.32, fontFace: FB, fontSize: 13, color: C.grey, margin: 0, isTextBox: true, valign: "middle" });
  });
  card(s, 0.6, 2.68, 7.35, 4.12, C.cardB);
  s.addText("WHAT WE DELIVER", { x: 0.88, y: 2.84, w: 6.8, h: 0.3, fontFace: FB, fontSize: 16, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 2 });
  s.addText([
    { text: "Agent A, Email Order Intake. ", options: { bold: true, color: C.title } },
    { text: "Processes all Customer POs received by email into Salesforce and is designed to replace the Existing RPA: reads the PO (Gemini, Document AI), maps fields directly to SAP and validates against SAP master data with no mapping database, checks price, contract, availability and duplicates, creates the sales order and updates the original Salesforce case. In Phase 1 an Ingredion reviewer confirms every result before the order is created.", options: { breakLine: true } },
    { text: "Agent B, Pre-bill Validation. ", options: { bold: true, color: C.title } },
    { text: "Adds a PO alignment check between invoice-ready and invoice-sent: assembles the evidence from SAP, PROS, Salesforce, Ariba, TermSync and the contract and fuel-rate files, compares price, freight and surcharge, quantity and payment terms with the PO, explains each gap and drafts the PO-update request for a named owner. Read-only: no change to SAP or PROS, no invoice released, no Customer contacted.", options: {} },
  ], { x: 0.88, y: 3.2, w: 6.8, h: 2.3, fontFace: FB, fontSize: 12, color: C.text, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 6 });
  s.addText("PRINCIPLES", { x: 0.88, y: 5.45, w: 6.8, h: 0.28, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true, charSpacing: 2 });
  bullets(s, [
    "Generative AI reads and drafts (A2, A3, A6; B3, B6); ordinary, testable code writes; a person approves every output.",
    "Managed code on Cloud Run, Gemini on Vertex AI, Model Armor guardrails, a per-case audit trail and dashboards; every exit recorded on the original record with a reason code.",
  ], 0.88, 5.75, 6.8, 0.95, { fontSize: 12 });
  card(s, 8.25, 2.68, 4.5, 4.12, C.cardA);
  s.addText("OUT OF SCOPE", { x: 8.53, y: 2.84, w: 3.95, h: 0.3, fontFace: FB, fontSize: 14, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 2 });
  s.addText("Ingredion-owned", { x: 8.53, y: 3.22, w: 3.95, h: 0.26, fontFace: FB, fontSize: 13, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Existing RPA and PO Portal changes; RPA retirement", "Master-data, CMIR and SAP-side fixes (reported, not made)", "GCP projects, IAM, connectivity, licences, cloud costs", "SIEM / NTT Vista integration; SAP AI connection"], 8.53, 3.48, 3.95, 1.3, { fontSize: 11.5 });
  s.addText("Deferred or excluded", { x: 8.53, y: 4.82, w: 3.95, h: 0.26, fontFace: FB, fontSize: 13, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Customer emails without reviewer approval", "Post-order changes, credit memos, handwritten or non-English POs", "Other dispute types; SAP or PROS changes; invoice holds", "Phase 2 automation: Ingredion decides at Gate 5, then change control"], 8.53, 5.1, 3.95, 1.6, { fontSize: 11.5 });
  s.addNotes("Emphasise the principle: generative AI only in the reading and drafting steps; everything that writes is ordinary code; a person approves every output under this SOW. Phase 2 is Ingredion's decision at Gate 5.");
}

function stepStrip(s, steps, y) {
  const n = steps.length, gap = 0.1, w = (12.13 - gap * (n - 1)) / n;
  steps.forEach(([id, text, ai], i) => {
    const x = 0.6 + i * (w + gap);
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h: 0.95, fill: { color: ai ? C.green : C.cardA }, line: { color: ai ? C.green : C.border, width: 1 }, rectRadius: 0.06 });
    s.addText([{ text: id, options: { bold: true, fontSize: 13, breakLine: true } }, { text: text, options: { fontSize: 10.5 } }], { x: x + 0.06, y: y + 0.06, w: w - 0.12, h: 0.83, fontFace: FB, color: ai ? C.white : C.title, margin: 0, isTextBox: true, align: "center", valign: "middle" });
  });
  s.addText([{ text: "■ ", options: { color: C.green } }, { text: "generative AI on Vertex AI (Gemini)     ", options: {} }, { text: "■ ", options: { color: C.border } }, { text: "ordinary code", options: {} }], { x: 0.6, y: y + 1.0, w: 8, h: 0.26, fontFace: FB, fontSize: 10.5, color: C.grey, margin: 0, isTextBox: true });
}

// 5. Agent A
{
  const s = pres.addSlide();
  chrome(s, { title: "Agent A: Email Order Intake Agent", subtitle: "SOW Part A · ten steps on Google Cloud, generative AI in three of them, one human judgment gate before anything reaches SAP" });
  stepStrip(s, [["A1", "Pick up the case", false], ["A2", "Classify the email", true], ["A3", "Read the PO", true], ["A4", "Map to SAP & validate", false], ["A5", "Rules & confidence", false], ["A6", "Exceptions & draft", true], ["A7", "Review summary · gate", false], ["A8", "Build SAP payload", false], ["A9", "Create order · incompletion log", false], ["A10", "Update Salesforce case", false]], 1.45);
  const cards = [
    ["FIRST RELEASE (SOW 2.4)", ["All email order cases, cohort by cohort; the Existing RPA stays as fallback until Ingredion retires it", "PDF, scanned, Excel, Word and email-body POs; an email with several POs becomes separate orders", "Master-data validation incl. CMIR; quantities converted to the SAP sales unit; no mapping database", "Price, contract, availability and duplicate checks flagged to the reviewer", "Post-creation incompletion log recorded on the case; reviewer confirms every result (Phase 1)"]],
    ["THE BASELINE WE REPLACE", ["June to July 2026: 4,000 cases, 1,500 errors, a 62.5% no-touch rate", "1,180 classified failures across 133 Customers and 16 error types", "45% extraction, 37% mapping data, 15% SAP, 3% MAX load", "Half of today's failure types cannot recur by design; a third depend on data existing in SAP; 13% are duplicates to route"]],
    ["OUTCOMES & SCORECARD (SOW 2.7)", ["Agent-created · Agent-assisted · Returned to the manual queue with a reason code", "Completion rate judged against the RPA's automation rate on the same cohort", "Field-level accuracy, undetected errors, reviewer confirmation, handling time, run cost", "Thresholds set at Gate 1 from the backtest on 500 past POs"]],
  ];
  cards.forEach(([h, items], i) => {
    const x = 0.6 + i * 4.11;
    card(s, x, 2.85, 3.91, 3.95, i === 1 ? C.cardB : C.cardA);
    s.addText(h, { x: x + 0.22, y: 3.0, w: 3.5, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
    bullets(s, items, x + 0.22, 3.38, 3.5, 3.3, { fontSize: 11.5 });
  });
  s.addNotes("Ten steps from SOW section 2.3. Three use Gemini (classification, extraction, drafting the clarification). The human judgment gate sits after A7; nothing reaches SAP without a reviewer in Phase 1. The baseline figures come from Ingredion's error analysis received on 23 October.");
}

// 6. Agent B
{
  const s = pres.addSlide();
  chrome(s, { title: "Agent B: Pre-bill Validation Agent", subtitle: "SOW Part B, Pre-bill Validation and Dispute Prevention · eight steps, generative AI in two, read-only; rules decide, AI explains, people act" });
  stepStrip(s, [["B1", "Pick up the invoice-ready order", false], ["B2", "Assemble the evidence", false], ["B3", "Read the PO", true], ["B4", "Normalise & match lines", false], ["B5", "Compare (four checks)", false], ["B6", "Explain & draft", true], ["B7", "Route to the owner · gate", false], ["B8", "Record", false]], 1.45);
  const cards = [
    ["FOUR CHECKS, THREE OUTCOMES", ["Price must match exactly after unit and currency conversion", "Freight and surcharge: any charge not on the PO is flagged", "Quantity within the PO range; over-shipments first", "Payment terms must match exactly", "Outcomes: Matched · Updated PO required (Customer Service or Commercial sends the draft) · Fix our side or decide (CBA, Sales, PROS)"]],
    ["ANCHOR CASE: KRAFT HEINZ", ["SO 809-6862: price USD 40.14 per CWT on the PO against 47.00 on the invoice", "USD 300 fuel surcharge added at shipment, not on the PO", "170,250 lb shipped against 170,000 lb ordered", "110 days on the invoice against 120 days on the PO", "The first release must catch all four; our evaluation suite already returns 4 of 4 with no false alarms"]],
    ["SIZE & SCORECARD (SOW 3.2, 3.4)", ["26,860 open or late invoices in the United States and Canada (6 August 2026)", "3,155 coded Pricing Discrepancy; 674 Freight Bill Disputed", "Catch rate at least 95%, false alarms at most 10%, traceability 100%", "Reviewer agreement at least 85%, time saved at least 30%, zero actions without a person"]],
  ];
  cards.forEach(([h, items], i) => {
    const x = 0.6 + i * 4.11;
    card(s, x, 2.85, 3.91, 3.95, i === 1 ? C.cardB : C.cardA);
    s.addText(h, { x: x + 0.22, y: 3.0, w: 3.5, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
    bullets(s, items, x + 0.22, 3.38, 3.5, 3.3, { fontSize: 11.5 });
  });
  s.addNotes("Eight steps from SOW section 3.3. The agent writes to nothing: its outputs are the review queue, the drafted PO-update request and its own audit trail. The invoice-ready definition is agreed in Stage 2; the variances are confirmed at Gate 1.");
}

// 7. Key differentiators
{
  const s = pres.addSlide();
  chrome(s, { title: "Key Differentiators: What Changes", subtitle: "From the Existing RPA and today's manual pre-bill handling to the two agents" });
  table(s, ["Area", "Today", "With the agent"], [
    { band: "Email Order Intake" },
    ["Reading the PO", "A per-Customer OCR model (Form Recognizer); 45% of failures are extraction", "Gemini on Vertex AI reads any layout; Document AI for scans; confidence per field feeds the review"],
    ["Validation", "A SQL mapping database and stored procedures; 37% of failures are mapping data", "Direct validation against SAP master data incl. CMIR; units converted with SAP's own factors"],
    ["Scope", "Failed cases only were in the earlier draft", "All email orders, cohort by cohort; the RPA keeps unmoved cohorts and stays as fallback"],
    ["Failures", "1,500 of 4,000 cases to rework: bot retry, data fixes, manual entry", "Every case stops at a reviewer with reason codes; half of today's failure types cannot recur; duplicates are classified at intake"],
    ["Platform", "Power Automate, Logic Apps, a trained model per Customer", "Managed code on Cloud Run with tests, pipelines, a per-case audit trail, dashboards and a kill switch"],
    { band: "Pre-bill Validation" },
    ["The check", "No check between invoice-ready and invoice-sent; the Customer portal finds the gap", "A PO alignment step at invoice-ready: four checks against the agreed variances"],
    ["The evidence", "Six sources searched by hand after a rejection", "Evidence assembled automatically with every result traceable to its record"],
    ["The follow-up", "Nobody owns the request for an updated PO after shipment", "A named owner per outcome receives the explanation and a drafted PO-update request"],
  ], { y: 1.5, colW: [1.9, 4.6, 5.63], fontSize: 12, headerSize: 13, bandRows: [1] });
  s.addNotes("The point of this slide is the design change the SOW made: direct SAP validation without the mapping database, generative reading without per-Customer models, and a named owner for the pre-bill gap.");
}

// 8. Delivery approach
{
  const s = pres.addSlide();
  chrome(s, { title: "Delivery Approach: Six Stages, Six Gates", subtitle: "Each stage ends with a documented go/no-go by Ingredion within 5 working days of the gate review (SOW 4.2); stages 2 to 6 start only on a go at Gate 1" });
  const stages = [
    ["1", "Discovery & Assessment", "3 weeks + Week 0", "Baseline, exception or gap map, target architecture, prototype and backtest, business case", "Gate 1: go/no-go for build; validation location decided; thresholds and plan confirmed", ["Both agents: Fri 20 Nov 2026"]],
    ["2", "Solution Design", "2 weeks", "Requirements and acceptance criteria, solution design, integration specification, environment design, test plan", "Gate 2: formal design approval; architecture and security review complete", ["Both agents: Fri 4 Dec 2026"]],
    ["3", "Build", "A: 5 weeks · B: 4 weeks", "Dev pipelines, the agent, integration components, evaluation suite, dashboards, build documentation and test cases", "Gate 3: requirements built, evaluation passing in Dev, documentation and test cases delivered", ["A: Fri 8 Jan 2027", "B: Fri 1 Jan 2027 (review on 30 or 31 Dec)"]],
    ["4", "Test & Validation", "3 weeks", "SIT, evaluation on unseen cases, UAT support, performance and security testing (SOW 5.4), release readiness pack with run model", "Gate 4: UAT signed off, thresholds met, no open critical or high findings, production change approved", ["A: Fri 29 Jan 2027", "B: Fri 22 Jan 2027"]],
    ["5", "Production Release", "A: 4 weeks · B: 3 weeks", "Production deployment, shadow mode, then assisted mode with reviewers or owners", "Gate 5: shadow and assisted reports meet the Gate 1 thresholds; Phase 2 decision", ["A: Fri 26 Feb 2027", "B: Fri 12 Feb 2027"]],
    ["6", "Hyper Care & Handover", "4 weeks", "Monitoring and tuning, runbook and guides, Knowledge Transition to the AMS partner, closure report", "Gate 6: run owner accepts; Ingredion and the AMS partner sign off the Knowledge Transition", ["A: Fri 2 Apr 2027", "B: Fri 19 Mar 2027"]],
  ];
  const w = 1.92, gap = 0.12;
  stages.forEach(([n, name, dur, deliv, gate, when], i) => {
    const x = 0.6 + i * (w + gap);
    // The chevron's left notch is 0.375 in deep at this height; the text starts clear of it.
    s.addShape(pres.ShapeType.chevron, { x, y: 1.5, w: w + 0.1, h: 0.75, fill: { color: i % 2 === 0 ? C.green : "6AA84F" }, line: { color: C.white, width: 1 } });
    s.addText([{ text: `Stage ${n}`, options: { bold: true, fontSize: 12, breakLine: true } }, { text: name, options: { fontSize: 10.5 } }], { x: x + 0.45, y: 1.52, w: w - 0.6, h: 0.7, fontFace: FB, color: C.white, margin: 0, isTextBox: true, valign: "middle" });
    card(s, x, 2.4, w, 4.4, i % 2 === 0 ? C.cardA : C.cardB);
    s.addText(dur, { x: x + 0.12, y: 2.5, w: w - 0.24, h: 0.28, fontFace: FB, fontSize: 11.5, bold: true, color: C.green, margin: 0, isTextBox: true });
    s.addText(deliv, { x: x + 0.12, y: 2.82, w: w - 0.24, h: 1.5, fontFace: FB, fontSize: 10.5, color: C.text, margin: 0, isTextBox: true, valign: "top" });
    s.addText(gate, { x: x + 0.12, y: 4.4, w: w - 0.24, h: 1.3, fontFace: FB, fontSize: 10.5, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "top" });
    s.addShape(pres.ShapeType.line, { x: x + 0.12, y: 5.78, w: w - 0.24, h: 0, line: { color: C.border, width: 1 } });
    s.addText("GATE REVIEW", { x: x + 0.12, y: 5.86, w: w - 0.24, h: 0.22, fontFace: FB, fontSize: 9, bold: true, color: C.green, margin: 0, isTextBox: true, charSpacing: 1 });
    s.addText(when.map((t, k) => ({ text: t, options: { breakLine: k < when.length - 1 } })), { x: x + 0.12, y: 6.08, w: w - 0.24, h: 0.65, fontFace: FB, fontSize: 10.5, color: C.text, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 2 });
  });
  s.addNotes("The same six stages for both agents; durations differ in Build and Production Release because Agent B creates nothing in SAP. A no-go at Gate 1 closes that agent with its Stage 1 deliverables; the other agent continues.");
}

// 9. Timeline
{
  const s = pres.addSlide();
  chrome(s, { title: "Timelines: Stages, Gates and Dates", subtitle: "Weeks counted from Week 0 = 26 October 2026; Stage 1's three weeks count from the day access and the sample are both in place (SOW 8.2(c))" });
  table(s, ["#", "Stage", "Agent A · Email Order Intake", "Agent B · Pre-bill Validation", "Gate (Friday of the gate week) · decided by"], [
    ["0", "Mobilisation", "Week 0 · 26 to 30 Oct 2026", "Week 0 · 26 to 30 Oct 2026", "Access and samples in place"],
    ["1", "Discovery & Assessment", "Weeks 1 to 3 · 2 to 20 Nov", "Weeks 1 to 3 · 2 to 20 Nov", "Gate 1 · 20 Nov 2026 · Sponsor"],
    ["2", "Solution Design", "Weeks 4 to 5 · 23 Nov to 4 Dec", "Weeks 4 to 5 · 23 Nov to 4 Dec", "Gate 2 · 4 Dec 2026 · Technical lead"],
    ["3", "Build", "Weeks 6 to 10 · 7 Dec to 8 Jan 2027", "Weeks 6 to 9 · 7 Dec to 1 Jan 2027", "Gate 3 · 8 Jan (A) · 1 Jan (B) · Sponsor"],
    ["4", "Test & Validation", "Weeks 11 to 13 · 11 to 29 Jan", "Weeks 10 to 12 · 4 to 22 Jan", "Gate 4 · 29 Jan (A) · 22 Jan (B) · Sponsor"],
    ["5", "Production Release", "Weeks 14 to 17 · 1 to 26 Feb (shadow 2 weeks, assisted 2 weeks)", "Weeks 13 to 15 · 25 Jan to 12 Feb (shadow 1 week, assisted 2 weeks)", "Gate 5 · 26 Feb (A) · 12 Feb (B) · Sponsor"],
    ["6", "Hyper Care & Handover", "Weeks 18 to 21 · 1 to 26 Mar; closure week 22", "Weeks 16 to 19 · 15 Feb to 12 Mar; closure week 20", "Gate 6 · 2 Apr (A) · 19 Mar (B) · Run owner and AMS partner"],
  ], { y: 1.5, colW: [0.45, 2.2, 3.35, 3.35, 2.78], fontSize: 12, headerSize: 12.5 });
  s.addText("Calendar risks already visible: Diwali 6 Nov (week 1) · Thanksgiving 26 to 27 Nov (week 4, the design review window before Gate 2) · Christmas 24 to 25 Dec and New Year 1 Jan (build weeks; Agent B's Gate 3 week).", { x: 0.6, y: 6.35, w: 12.13, h: 0.5, fontFace: FB, fontSize: 11, italic: true, color: C.grey, margin: 0, isTextBox: true });
  s.addNotes("Dates are the Fridays of the gate weeks from the WBS of 23 October. Ingredion then has 5 working days for the gate decision. Any slip in access or the sample moves the affected agent's timeline day for day.");
}

// 10. Deliverables and exit criteria
{
  const s = pres.addSlide();
  chrome(s, { title: "Deliverables and Gate Exit Criteria", subtitle: "A-D1 to A-D26 and B-D1 to B-D26 (SOW 2.6, 3.7); each deliverable is reviewed within 5 working days and silence is acceptance" });
  table(s, ["Stage", "Deliverables (A- / B- numbering)", "Done by (A / B)", "Gate exit criteria (SOW 4.2)"], [
    ["1 Discovery", "D1 baseline and classification · D2 exception map / test-case set and gap map · D3 target architecture · D4 interim review · D5 prototype and backtest report · D6 business case and pilot plan · D7 executive readout", "20 Nov 2026", "Architecture approved, validation location decided, thresholds (and variances) and the plan for Stages 2 to 6 confirmed"],
    ["2 Design", "D8 requirements and acceptance criteria · D9 solution design · D10 integration specification · D11 environment and deployment design · D12 test and evaluation plan", "4 Dec 2026", "Formal design approval by the technical lead; architecture and security review complete"],
    ["3 Build", "D13 Dev environment and pipelines · D14 the agent · D15 integration components · D16 evaluation suite, build test report, dashboards · D16a build documentation · D16b baseline test cases · D16c developer test cases with results", "8 Jan / 1 Jan 2027", "Requirements built, automated evaluation passing in Dev, documentation and test cases delivered, release ready for Test"],
    ["4 Test", "D17 Test environment · D18 SIT and evaluation report · D19 UAT, performance and security report · D20 release readiness pack (release notes, rollback plan rehearsed, go-live checklist, run model)", "29 Jan / 22 Jan 2027", "UAT signed off, thresholds met, SOW 5.4 testing complete with no open critical or high findings, run model agreed, production change approved"],
    ["5 Production", "D21 production deployment · D22 shadow mode report · D23 assisted mode report", "26 Feb / 12 Feb 2027", "Shadow and assisted reports meet the Gate 1 thresholds; Phase 2 (A) or later dispute types (B) decided"],
    ["6 Hyper care", "D24 hyper care report · D25 runbook, reviewer or owner guide, knowledge transfer and Knowledge Transition sign-off · D26 closure report", "2 Apr / 19 Mar 2027", "Run owner accepts the handover; Ingredion and the AMS partner sign off the Knowledge Transition; all work product in Ingredion's repository"],
  ], { y: 1.5, colW: [1.4, 5.5, 1.5, 3.73], fontSize: 11, headerSize: 12.5, bandRows: [1] });
  s.addNotes("Deliverables go into Ingredion's repository under docs/deliverables so that the Gate 6 condition is true by construction. The SOW adds D16a to D16c in Stage 3 and the run model in D20.");
}

// 11. Stage 1 plan
{
  const s = pres.addSlide();
  chrome(s, { title: "Stage 1 Plan: Weeks 1 to 3", subtitle: "2 to 20 November 2026 · both agents in parallel · Gate 1 go/no-go on Friday 20 November" });
  const weeks = [
    ["Week 1 · 2 to 6 Nov", "MOBILISATION & WALKTHROUGHS", ["Walkthroughs: email-to-SAP flow and problem-case recordings; invoice-ready to invoice-sent flow and dispute handling", "Baselines started: the June to July failure analysis validated against the sample; the 6 August root-cause analysis validated", "SAP interfaces, incompletion log, field mapping and unit conversions confirmed; read interface or extract per pre-bill source", "Dev project live: first Gemini call, Document AI processor, Model Armor template wired", "Prototype build starts on the samples; access verified and escalated beyond the 5-day period", "Diwali on Friday 6 November"]],
    ["Week 2 · 9 to 13 Nov", "PROTOTYPE & INTERIM REVIEW", ["Prototype in Dev on approved historical data: A2 to A4 (classify, extract, map and validate); B2 to B6 (evidence, PO, normalise, compare, explain)", "Reference results confirmed by Ingredion: final SAP orders (A), correct outcome per test case (B)", "Interim review with the sponsor (serves as the steering review)", "Target architecture drafts with the validation-location options (SAP or GCP)", "Business-case inputs: handling time and volumes per cohort; preventable share of disputes"]],
    ["Week 3 · 16 to 20 Nov", "BACKTEST, READOUT, GATE 1", ["Backtest reports: 500 past POs scored field by field against the final SAP orders; past orders scored by check against the scorecard, anchor case 4 of 4", "Exception map and order format analysis (A-D2); test-case set and gap map (B-D2)", "Target architecture with the validation-location recommendation (A-D3, B-D3)", "Business case and pilot plan for Stages 2 to 6 (A-D6, B-D6); proposed thresholds and variances", "Executive readout (A-D7, B-D7) and the Gate 1 go/no-go for each agent"]],
  ];
  weeks.forEach(([h, sub, items], i) => {
    const x = 0.6 + i * 4.11;
    card(s, x, 1.5, 3.91, 5.3, i % 2 === 0 ? C.cardA : C.cardB);
    s.addText(h, { x: x + 0.25, y: 1.65, w: 3.5, h: 0.32, fontFace: FB, fontSize: 16, bold: true, color: C.title, margin: 0, isTextBox: true });
    s.addText(sub, { x: x + 0.25, y: 1.98, w: 3.5, h: 0.26, fontFace: FB, fontSize: 10.5, bold: true, color: C.green, margin: 0, isTextBox: true, charSpacing: 1 });
    bullets(s, items, x + 0.25, 2.35, 3.45, 4.35, { fontSize: 12 });
  });
  s.addNotes("Stage 1 only works if the Week 0 items land: the sample within 5 working days, the Dev project, the data approval and the prototype security review. Week 3 ends with the executive readout and the Gate 1 decision for each agent.");
}

// 12. Team roles and responsibilities
{
  const s = pres.addSlide();
  chrome(s, { title: "Team Roles & Responsibilities", subtitle: "Parkar staffing per Appendix 3 of the SOW; committed capacity is not reduced and key persons are not replaced without Ingredion's approval (SOW 8.2(c))" });
  table(s, ["Role", "Location", "Agent A", "Agent B", "Allocation"], [
    ["AI Engineer", "Offshore (Pune)", "Ananya Mehta", "Isha Chandravanshi", "Full time, one per agent"],
    ["AI Engineer", "Offshore (Pune)", "Anshika Ranjan", "Abhishek Nage", "Full time, one per agent"],
    ["Data Engineer", "Offshore (Pune)", "Eshita Khare", "Eshita Khare", "50% for each agent"],
    ["QA Engineer", "Offshore (Pune)", "Sanjana Sulakhe", "Sanjana Sulakhe", "50% for each agent"],
    ["SAP S&D SME", "Offshore", "To be named", "To be named", "20 hours per week"],
    ["Technical Lead / TPM", "Offshore (Pune)", "Dnyaneshwar N. Bairagi", "Dnyaneshwar N. Bairagi", "50% overall"],
    ["Forward Deployed Engineer", "Onsite, Westchester IL", "Shanmukhi Neelam", "Shanmukhi Neelam", "40 hours per week"],
    ["Onsite Business Analyst", "Onsite, Westchester IL", "Niti Bhargava", "Niti Bhargava", "20 hours per week"],
  ], { x: 0.6, y: 1.5, w: 8.1, colW: [1.9, 1.75, 1.6, 1.6, 1.25], fontSize: 11.5, headerSize: 12 });
  s.addText("Eshita Khare and Isha Chandravanshi are both Data and AI Engineers and may be used interchangeably. Program management and the Solution Architect / Sr. Tech Lead are shared Parkar roles, not charged separately (SOW 11.4).", { x: 0.6, y: 5.9, w: 8.1, h: 0.75, fontFace: FB, fontSize: 10.5, italic: true, color: C.grey, margin: 0, isTextBox: true });
  card(s, 8.95, 1.5, 3.78, 5.3, C.cardA);
  s.addText("RACI IN BRIEF (APPENDIX 2)", { x: 9.2, y: 1.65, w: 3.3, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
  s.addText("Parkar", { x: 9.2, y: 2.05, w: 3.3, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Design, build, test, deploy and tune both agents; all deliverables", "Delivery plan, RAID log, weekly reporting, change requests", "Run model, runbook, Knowledge Transition to the AMS partner"], 9.2, 2.33, 3.3, 1.35, { fontSize: 11 });
  s.addText("Ingredion", { x: 9.2, y: 3.75, w: 3.3, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Access, environments, data, approvals and decisions within 5 working days", "Gate decisions; UAT sign-off; reviewers and owners; the run owner", "Changes on the SAP, Salesforce and RPA side by the Gate 2 dates; management of Accenture, NTT Data and Infosys"], 9.2, 4.03, 3.3, 1.6, { fontSize: 11 });
  s.addText("Shared", { x: 9.2, y: 5.7, w: 3.3, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Release approval of every prompt, model, threshold, rule or variance change after evaluation"], 9.2, 5.98, 3.3, 0.7, { fontSize: 11 });
  s.addNotes("Staffing from the plan of 26 October. Confirm the SAP S&D SME name this week. Escalation: Hardik Desai (AVP Cloud AI) level 1, Amit Gandhi (CTO) level 2, per SOW 6.2.");
}

// 13. Prerequisites: access and enablement
{
  const s = pres.addSlide();
  chrome(s, { title: "Pre-requisites: Access & Enablement", subtitle: "The Stage 1 clock starts only when access and the historical sample are both in place (SOW 8.2(c)); every request goes into the RAID log the day it is raised" });
  const rows = [
    ["Team onboarding", ["User IDs, VPN or remote access for the Pune team, a shared Teams channel, Westchester badge and network access", "Security induction for the Parkar team; Ingredion identity used for Git and gcloud"], "Ingredion IT  ·  Week 0"],
    ["Google Cloud foundation", ["Dev project with Vertex AI (approved Gemini models, quota), Document AI, Model Armor, Cloud Run, Secret Manager, Logging and Trace; Test and Prod projects in Stage 3", "Dedicated service accounts with least-privilege IAM, region decided; one repository per agent in Ingredion's Git platform with pipeline permissions"], "GCP platform team  ·  Week 0"],
    ["Data & approvals", ["500 past email POs with final SAP orders, and the sample of past invoiced orders incl. Kraft Heinz 809-6862, within 5 working days of start", "Data classification and AI-use approval with the approved model list; Model Armor template; prototype security review within 5 working days of the request"], "Use-case leads / Security  ·  by 2 Nov"],
    ["System access", ["SAP reads (master data, CMIR, pricing, contract, availability, orders, incompletion log) or the GCP data sources; Salesforce API, sandbox and cohort routing; Microsoft Graph (drafts only)", "Pre-bill sources: SAP billing and freight, PROS, Salesforce PO documents, Ariba, TermSync, contract and fuel-rate files (read interface or scheduled extract)"], "SAP / Salesforce / M365 / system owners  ·  Weeks 1 to 2"],
    ["Connectivity & decisions", ["Path from the GCP projects to SAP API Management on Azure, Salesforce and Graph (allow-listed egress or private connectivity)", "Cohort routing approach (Gate 2), invoice-ready signal (Stage 2), variances and owners (Gate 1), retention policy (Stage 2)"], "Network & Security / use-case leads  ·  decision Week 0"],
  ];
  rows.forEach(([h, items, owner], i) => {
    const y = 1.5 + i * 1.06;
    card(s, 0.6, y, 12.13, 0.96, i % 2 === 0 ? C.cardA : C.cardB);
    circle(s, 0.82, y + 0.28, 0.4, String(i + 1), 13);
    s.addText(h, { x: 1.38, y: y + 0.08, w: 2.45, h: 0.8, fontFace: FB, fontSize: 17, bold: true, color: C.title, margin: 0, isTextBox: true, valign: "middle" });
    bullets(s, items, 3.95, y + 0.1, 5.9, 0.8, { fontSize: 10.5, paraSpaceAfter: 2 });
    s.addText(owner, { x: 9.95, y: y + 0.08, w: 2.65, h: 0.8, fontFace: FB, fontSize: 11.5, bold: true, color: C.green, margin: 0, isTextBox: true, valign: "middle", align: "right" });
  });
  s.addNotes("These are the items in the requirements list sent on 23 October (28 items for Agent A, B1 to B8 for Agent B). The five groups here are what decides whether Stage 1 starts on day one.");
}

// 14. Prerequisites: data and artefacts
{
  const s = pres.addSlide();
  chrome(s, { title: "Pre-requisites: Data & Artefacts", subtitle: "What the Stage 1 baselines and backtests need, who provides it and where it stands today" });
  table(s, ["Artefact", "Needed for", "Owner", "Needed by", "Status"], [
    ["RPA failure analysis, June to July 2026 (1,180 failed cases, 16 error types, ship-to view, no-touch baseline)", "Baseline A-D1, exception map A-D2", "Ingredion (provided)", "Week 0", { text: "Received 23 Oct", bold: true, color: C.green }],
    ["Full case population for the period (about 4,000 cases) with outcomes by Customer and ship-to", "Automation rate per cohort; drawing the sample", "Use-case lead, Order Intake", "Week 0", "Pending"],
    ["Historical sample: 500 past email POs incl. RPA-failed, with attachments, RPA and OCR output, failure reasons and final SAP orders", "Backtest A-D5; the Stage 1 clock", "Use-case lead, Order Intake", "2 Nov 2026", "Pending"],
    ["Reference results confirmed: the final SAP orders are correct", "Field-level accuracy measurement", "Use-case lead, Order Intake", "13 Nov 2026", "Pending"],
    ["Sample of past invoiced orders incl. Kraft Heinz SO 809-6862 with PO, SAP order, delivery and billing data and the confirmed outcome", "Test cases B-D2, backtest B-D5", "Use-case lead, Pre-bill; Pricing & Billing", "2 Nov 2026", "Pending"],
    ["Root-cause analysis of 6 August 2026 and the solution brief of 7 October 2026", "Baseline B-D1", "Ingredion (provided)", "Week 0", { text: "Received", bold: true, color: C.green }],
    ["SAP field requirements and mapping, pricing and contract sources; recordings of problem cases", "A-D3, payload A8, A5 checks", "SAP team; use-case lead", "Weeks 0 to 1", "Pending"],
    ["Business rules: variances per check, source-wins rule, portal rules, freight and fuel-rate source, unit and currency rules", "B5 rules, requirements B-D8", "Pricing & Billing; Commercial", "Gate 1, 20 Nov", "Pending"],
    ["Named owner per outcome and human step; review-queue users and the notification channel", "B7 routing", "Sponsor; use-case lead, Pre-bill", "Stage 1 / Gate 2", "Pending"],
    ["SOW No. 07 signature, Appendix 3 staffing plan, Ingredion Project Manager named", "Start of the engagement", "Parkar and Ingredion", "26 Oct 2026", "In progress"],
  ], { y: 1.5, colW: [4.6, 2.5, 2.1, 1.3, 1.63], fontSize: 10.5, headerSize: 12 });
  s.addNotes("Eight of the ten lines are Ingredion dependencies. Confirm owners and dates for the pending items today; the two samples are due within 5 working days of the start.");
}

// 15. Risks
{
  const s = pres.addSlide();
  chrome(s, { title: "Risks, Dependencies & Mitigation", subtitle: "Dependencies on Ingredion or its providers are recorded in the RAID log with their expected impact (SOW 8.2(c), dependency attribution)" });
  table(s, ["#", "Risk or dependency", "Impact if left", "Mitigation", "Owner"], [
    ["1", "Week-0 inputs arrive late: samples, Dev project, data approval, security review", "The Stage 1 clock does not start; every later date moves day for day", "Raise every request in Week 0 and log it in the RAID log; prototype and harness built on fixtures meanwhile", "Ingredion leads; Parkar TPM"],
    ["2", "Connectivity from the GCP projects to SAP API Management, Salesforce and Graph is undecided", "Everything is granted but unreachable; network changes take weeks across three parties", "Decide the method in Week 0 (allow-listed egress or private connectivity); request the connector and NAT address now", "Ingredion network and security"],
    ["3", "Five-working-day reviews inside a two-week Stage 2, with Thanksgiving in week 4", "Gate 2 slips, and Build with it", "Submit D9 and D10 by Monday 30 November; walk Ingredion through drafts during week 4", "Parkar; Ingredion technical lead"],
    ["4", "Christmas and New Year fall in Stage 3; Agent B's Gate 3 week contains 1 January", "Reduced build capacity; gate review timing", "Front-load build parts 1 and 2; hold the Agent B Gate 3 review on 30 or 31 December; write D16a to D16c during the build", "Parkar TPM"],
    ["5", "The failure analysis holds failures only; the 500-PO sample must represent the full mix", "Thresholds set on the wrong population; business case does not hold", "Draw the sample from the full population in the June to July mix; reference results confirmed by 13 November", "Use-case lead, Order Intake"],
    ["6", "A third of today's failures depend on master data existing in SAP (CMIR)", "Those cases are reported, not completed; completion rate lower than expected", "Measure the share in Stage 1 with a CMIR extract for the 396 cases; report to Ingredion per SOW 10.2", "SAP team"],
    ["7", "Reviewer and owner capacity at primary volume", "The review queue becomes the new manual backlog", "Shadow each cohort first and size capacity before cut-over; owners named in Stage 1; reviewers nominated by Stage 3", "Use-case leads"],
    ["8", "Invoice-ready signal and variances are defined only in Stage 2 and at Gate 1", "B1 and B5 cannot be fixed in the design", "Candidate signal confirmed in Stage 1; variances and portal rules as configuration, not code", "SAP team; Pricing & Billing"],
    ["9", "SOW 1.7: pre-existing materials and code only in Ingredion's repository", "Dispute at closure; licence questions for the AMS partner", "Declare the shared factory runtime in writing before Stage 3; develop in Ingredion's repositories from Week 0", "Parkar engagement lead"],
  ], { y: 1.5, colW: [0.4, 3.3, 2.9, 3.9, 1.63], fontSize: 10.5, headerSize: 12 });
  s.addNotes("Walk the top three if time is short: the Week-0 inputs, the connectivity decision and the Stage 2 review window. Everything here is also in the WBS risk column.");
}

// 16. Communication and governance
{
  const s = pres.addSlide();
  chrome(s, { title: "Communication & Governance Framework", subtitle: "One governance structure covers both agents (SOW 9.0); Parkar's program manager and Forward Deployed Engineer are the day-to-day counterparts of the Ingredion technical lead and use-case leads" });
  table(s, ["Forum or artefact", "Purpose", "Participants", "Frequency"], [
    ["Daily stand-up", "Progress, impediments, blockers across onsite and offshore", "Parkar delivery team; Ingredion leads as needed", "Daily, in the overlap window"],
    ["Weekly status meeting and report", "Progress, RAID log, dependencies tracked against the 5-working-day periods, decisions needed", "Ingredion technical lead and use-case leads; Parkar PM, FDE, BA", "Weekly"],
    ["Steering review", "Direction, risks, decisions; the interim reviews and executive readouts serve as the Stage 1 steering reviews", "Ingredion sponsor and leads; Parkar engagement lead and PM", "Every 4 weeks and at each gate"],
    ["Gate review", "Documented go/no-go per agent against the SOW 4.2 criteria", "Ingredion sponsor (technical lead for Gate 2); Parkar", "End of each stage; decision within 5 working days"],
    ["RAID log and activity tracker", "Every risk, issue and dependency with an owner, due date and agent; deliverable submissions and acceptance", "Both teams", "Continuous; reviewed weekly"],
    ["Change control", "Scope, timeline or team changes; candidate changes recorded in the RAID log before any work outside scope", "Ingredion sponsor; Parkar engagement lead", "As needed (SOW 10.4)"],
  ], { x: 0.6, y: 1.5, w: 8.4, colW: [1.95, 3.1, 2.1, 1.25], fontSize: 10.5, headerSize: 12 });
  card(s, 9.25, 1.5, 3.48, 5.3, C.cardA);
  s.addText("ESCALATION & TURNAROUNDS", { x: 9.5, y: 1.65, w: 3.0, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
  s.addText("Parkar escalation (SOW 6.2)", { x: 9.5, y: 2.05, w: 3.0, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Level 1: Hardik Desai, AVP Cloud AI", "Level 2: Amit Gandhi, CTO"], 9.5, 2.33, 3.0, 0.7, { fontSize: 11 });
  s.addText("Issue escalation (SOW 9.0)", { x: 9.5, y: 3.05, w: 3.0, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Unresolved at working level for 5 working days: escalated to the Ingredion sponsor and Parkar's engagement lead, who decide within 3 working days"], 9.5, 3.33, 3.0, 0.95, { fontSize: 11 });
  s.addText("Ingredion periods (SOW 4.2, 8.1)", { x: 9.5, y: 4.3, w: 3.0, h: 0.26, fontFace: FB, fontSize: 12, bold: true, color: C.green, margin: 0, isTextBox: true });
  bullets(s, ["Decisions and deliverable reviews: 5 working days; silence is acceptance", "Gate decisions: 5 working days from the gate review", "Access requests after Week 0, prototype security review, UAT sign-off, production approval: 5 working days"], 9.5, 4.58, 3.0, 1.65, { fontSize: 11 });
  s.addText("Channels: MS Teams channel, email for minutes and handovers, the shared RAID log and tracker.", { x: 9.5, y: 6.25, w: 3.0, h: 0.5, fontFace: FB, fontSize: 10.5, italic: true, color: C.grey, margin: 0, isTextBox: true });
  s.addNotes("Confirm the day and time for the weekly status call, the stand-up slot and the first steering review before we leave the room.");
}

// 17. Next steps
{
  const s = pres.addSlide();
  chrome(s, { title: "Next Steps: This Week", subtitle: "Every line needs a named owner and a date before we finish" });
  table(s, ["Action", "Owner", "By"], [
    ["Sign SOW No. 07 (redline v2); Parkar provides Appendix 3 (staffing plan); Ingredion names its Project Manager", "Hardik Desai; Ingredion sponsor", "26 Oct"],
    ["Confirm the Ingredion sponsor, technical lead, use-case leads and SMEs for both agents", "Ingredion sponsor", "28 Oct"],
    ["Issue user IDs, remote access, the Teams channel and Westchester access for the Parkar team", "Ingredion IT", "30 Oct"],
    ["Provide the Dev GCP project with Vertex AI, Document AI and Model Armor enabled; service accounts; one repository per agent", "GCP platform team", "30 Oct"],
    ["Confirm data classification and approve AI use; list the approved models; create the Model Armor template", "Ingredion security", "30 Oct"],
    ["Decide the connectivity approach from the GCP projects to SAP API Management, Salesforce and Graph", "Ingredion network and security", "30 Oct"],
    ["Provide the 500-PO historical sample and the sample of past invoiced orders (incl. Kraft Heinz 809-6862)", "Use-case leads", "2 Nov"],
    ["Raise the SAP, Salesforce, Graph and pre-bill source access requests and the prototype security review request", "Dnyaneshwar N. Bairagi", "27 Oct"],
    ["Baseline the integrated plan, RAID log and tracker; schedule the weekly status, the interim review (week 2) and the executive readout (week 3)", "Dnyaneshwar N. Bairagi; Niti Bhargava", "28 Oct"],
    ["Declare the pre-existing materials (shared factory runtime) for approval and move the code into Ingredion's repositories", "Abhishek Nage; Hardik Desai", "30 Oct"],
  ], { x: 1.0, y: 1.5, w: 11.33, colW: [7.5, 2.7, 1.13], fontSize: 11.5, headerSize: 12.5 });
  s.addNotes("Close the meeting on this slide. The two samples and the Dev project decide whether Stage 1 starts on 2 November.");
}

// 18. Appendix
{
  const s = pres.addSlide();
  chrome(s, { title: "Appendix: Scorecards and Reference Documents" });
  card(s, 0.6, 1.5, 3.95, 5.3, C.cardA);
  s.addText("AGENT A SCORECARD (SOW 2.7)", { x: 0.85, y: 1.65, w: 3.5, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
  bullets(s, ["Completion rate: share of email order cases completed as SAP sales orders, judged against the RPA's rate on the same cohort", "Field-level accuracy against the reviewer-confirmed result and the final SAP order", "Undetected errors: errors in created orders that neither the agent nor the reviewer caught", "Reviewer confirmation without correction", "Handling time per case against the Stage 1 baseline", "Run cost and model consumption per case", "Thresholds set at Gate 1 from the backtest; Parkar's opening proposal: recovery 50% / 70% / 80%, undetected errors 2% then 0.5%"], 0.85, 2.05, 3.5, 4.6, { fontSize: 12 });
  card(s, 4.7, 1.5, 3.95, 5.3, C.cardB);
  s.addText("AGENT B SCORECARD (SOW 3.4)", { x: 4.95, y: 1.65, w: 3.5, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
  bullets(s, ["Catch rate: at least 95% of real gaps, including all four gaps in the anchor case", "False alarms: no more than 10% of flagged cases", "Traceability: 100% of results traceable to their evidence", "Reviewer agreement: at least 85% of outcomes confirmed", "Time saved: at least 30% against the Stage 1 baseline", "Actions without a person: zero", "Missing data: 100% of missing-data cases flagged, and no more than 15% of cases"], 4.95, 2.05, 3.5, 4.6, { fontSize: 12 });
  card(s, 8.8, 1.5, 3.93, 5.3, C.cardA);
  s.addText("REFERENCE DOCUMENTS", { x: 9.05, y: 1.65, w: 3.5, h: 0.3, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true, charSpacing: 1 });
  bullets(s, ["Statement of Work No. 07, Ingredion redline v2, 20 October 2026", "Work Breakdown Structures for both agents, 23 October 2026", "Client requirements list v1.2 (28 items, B1 to B8, 12 decisions)", "Ingredion Agent Workflows (architecture and engineering review)", "Build guides for Agent A and Agent B, 26 October 2026", "NA NoTouch Error Analysis, received 23 October 2026", "Pre-bill solution brief, 7 October 2026"], 9.05, 2.05, 3.5, 4.6, { fontSize: 12 });
  s.addNotes("Backup material for questions on measures and sources.");
}

// 19. Thank you
{
  const s = pres.addSlide();
  pageNo += 1;
  s.background = { color: C.white };
  card(s, 0.6, 1.1, 12.13, 5.3, C.cardA);
  s.addImage({ path: LOGO, x: 1.15, y: 1.75, w: 2.1, h: 1.43 });
  s.addText("Thank You", { x: 1.15, y: 3.45, w: 6.5, h: 0.7, fontFace: FT, fontSize: 38, bold: true, color: C.title, margin: 0, isTextBox: true });
  s.addText("Digital Solutions to Deliver Seamless Customer Experience", { x: 1.15, y: 4.2, w: 6.5, h: 0.4, fontFace: FB, fontSize: 14, italic: true, color: C.green, margin: 0, isTextBox: true });
  s.addText("Chicago  ·  Washington DC  ·  Atlanta  ·  Toronto  ·  Dubai  ·  Pune", { x: 1.15, y: 5.35, w: 7.0, h: 0.35, fontFace: FB, fontSize: 10.5, color: C.grey, margin: 0, isTextBox: true });
  [["WEB", "https://www.parkar.in", 2.2], ["EMAIL", "info@parkar.in", 3.3], ["PHONE", "+1 (844) 824-6686", 4.4]].forEach(([k, v, y]) => {
    s.addText(k, { x: 8.4, y, w: 3.9, h: 0.28, fontFace: FB, fontSize: 9, bold: true, color: C.green, margin: 0, isTextBox: true, charSpacing: 2 });
    s.addText(v, { x: 8.4, y: y + 0.28, w: 3.9, h: 0.35, fontFace: FB, fontSize: 13, bold: true, color: C.title, margin: 0, isTextBox: true });
  });
  s.addNotes("Thank the Ingredion team; confirm the first weekly status call before closing.");
}

pres.writeFile({ fileName: OUT }).then((f) => console.log("written", f));
