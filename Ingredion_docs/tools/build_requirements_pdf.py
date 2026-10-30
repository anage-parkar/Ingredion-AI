"""Build the interactive requirements PDF (reportlab), SOW No. 07 redline v2 edition:
cover, clickable contents, bookmarks, tickable checkboxes, tables, running header
and footer, metadata."""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

OUT = Path(sys.argv[1])
AUTHOR = "Abhishek Nage"
ORG = "Parkar"
TITLE = "Client requirements to start the Email Order Intake Agent"
DATE = "21 October 2026"
VERSION = "1.2 (SOW No. 07 redline v2)"

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Calibri", str(FONTS / "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Calibri-Bold", str(FONTS / "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Calibri-Italic", str(FONTS / "calibrii.ttf")))
pdfmetrics.registerFont(TTFont("Calibri-BoldItalic", str(FONTS / "calibriz.ttf")))
pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold", italic="Calibri-Italic", boldItalic="Calibri-BoldItalic")

NAVY = colors.HexColor("#1B2A4A")
ACCENT = colors.HexColor("#2F5BD8")
MUTED = colors.HexColor("#5C6774")
LINE = colors.HexColor("#CFD6E0")
BAND = colors.HexColor("#EEF2F7")
HEAD = colors.HexColor("#E3E9F3")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "title": ParagraphStyle("title", fontName="Calibri-Bold", fontSize=26, leading=31, textColor=NAVY),
    "subtitle": ParagraphStyle("subtitle", fontName="Calibri", fontSize=13, leading=17, textColor=MUTED),
    "kicker": ParagraphStyle("kicker", fontName="Calibri-Bold", fontSize=9.5, leading=12, textColor=ACCENT, spaceAfter=2),
    "h1": ParagraphStyle("h1", fontName="Calibri-Bold", fontSize=16, leading=20, textColor=NAVY, spaceBefore=12, spaceAfter=6, keepWithNext=True),
    "h2": ParagraphStyle("h2", fontName="Calibri-Bold", fontSize=12.5, leading=15, textColor=NAVY, spaceBefore=8, spaceAfter=4, keepWithNext=True),
    "body": ParagraphStyle("body", fontName="Calibri", fontSize=10.5, leading=14, textColor=colors.HexColor("#1B232D"), spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Calibri", fontSize=8.5, leading=11, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Calibri", fontSize=8.8, leading=11),
    "cellb": ParagraphStyle("cellb", fontName="Calibri-Bold", fontSize=8.8, leading=11),
    "cellh": ParagraphStyle("cellh", fontName="Calibri-Bold", fontSize=8.6, leading=10.5, textColor=NAVY),
    "band": ParagraphStyle("band", fontName="Calibri-Bold", fontSize=9, leading=11, textColor=NAVY),
    "check": ParagraphStyle("check", fontName="Calibri", fontSize=10.5, leading=14),
    "toc1": ParagraphStyle("toc1", fontName="Calibri", fontSize=11, leading=16, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName="Calibri", fontSize=10, leading=14, leftIndent=12, textColor=MUTED),
}


class Heading(Paragraph):
    _n = 0

    def __init__(self, text: str, level: int = 0) -> None:
        super().__init__(text, S["h1"] if level == 0 else S["h2"])
        self.level = level
        self.plain = text
        Heading._n += 1
        self.key = f"sec{Heading._n}"


class Checkbox(Flowable):
    _n = 0

    def __init__(self, size: float = 10) -> None:
        super().__init__()
        Checkbox._n += 1
        self.name = f"cb{Checkbox._n}"
        self.size = size

    def wrap(self, aw, ah):
        return (self.size, self.size)

    def draw(self):
        ax, ay = self.canv.absolutePosition(0, 0)  # form widgets take page coordinates
        self.canv.acroForm.checkbox(name=self.name, x=ax, y=ay, size=self.size, buttonStyle="check", borderWidth=0.8, borderColor=NAVY, fillColor=colors.white, textColor=NAVY, forceBorder=True)


class NumberedCanvas(rl_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self._draw_chrome(total)
            super().showPage()
        super().save()

    def _draw_chrome(self, total: int) -> None:
        self.saveState()
        self.setStrokeColor(LINE)
        self.setLineWidth(0.6)
        self.line(MARGIN, PAGE_H - 12 * mm, PAGE_W - MARGIN, PAGE_H - 12 * mm)
        self.setFont("Calibri", 8.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, PAGE_H - 10.5 * mm, TITLE)
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 10.5 * mm, f"{ORG} · Ingredion Agentic AI Factory · SOW No. 07")
        self.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
        self.drawString(MARGIN, 9 * mm, f"Prepared by {AUTHOR}, {ORG} · {DATE} · Internal")
        self.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


class Doc(BaseDocTemplate):
    def __init__(self, path: str) -> None:
        super().__init__(
            path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=20 * mm, bottomMargin=20 * mm,
            title=TITLE, author=AUTHOR, subject="Access, data and decisions needed from Ingredion before Stage 1 (SOW No. 07 redline v2, Google Cloud)",
            creator=f"{AUTHOR}, {ORG}", keywords="Ingredion, Email Order Intake, requirements, SOW No. 07, Google Cloud, Vertex AI",
        )
        frame = Frame(MARGIN, 20 * mm, CONTENT_W, PAGE_H - 40 * mm, id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN, id="cover", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="Cover", frames=[cover]), PageTemplate(id="Body", frames=[frame])])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Heading):
            self.canv.bookmarkPage(flowable.key)
            self.canv.addOutlineEntry(flowable.plain, flowable.key, level=flowable.level, closed=False)
            self.notify("TOCEntry", (flowable.level, flowable.plain, self.page, flowable.key))


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def table(header, rows, widths, *, bands=None, checkbox_col=False) -> Table:
    data = [[Paragraph(h, S["cellh"]) for h in header]]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD), ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
    ]
    r = 1
    for i, row in enumerate(rows):
        if bands and i in bands:
            data.append([Paragraph(bands[i], S["band"])] + [""] * (len(header) - 1))
            # keep the band label on the same page as the first row under it
            style += [("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), BAND), ("TOPPADDING", (0, r), (-1, r), 4), ("NOSPLIT", (0, r), (-1, r + 1))]
            r += 1
        cells = []
        for j, c in enumerate(row):
            if isinstance(c, Flowable):
                cells.append(c)
            else:
                bold = j == (1 if checkbox_col else 0) and len(header) > 2
                cells.append(Paragraph(str(c), S["cellb"] if bold else S["cell"]))
        data.append(cells)
        r += 1
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def checklist(items) -> Table:
    rows = [[Checkbox(), Paragraph(t, S["check"])] for t in items]
    t = Table(rows, colWidths=[7 * mm, CONTENT_W - 7 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (0, -1), 0)]))
    return t


# ── content (SOW No. 07, redline v2 of 20 October 2026) ──────────────────────

CALENDAR = [
    ("Week 0: mobilisation", "Week 0", "Week 0", "26 October 2026"),
    ("Gate 1: go/no-go for build", "Week 3", "Week 3", "16 November 2026"),
    ("Gate 2: design approval", "Week 5", "Week 5", "30 November 2026"),
    ("Gate 3: ready for test", "Week 10", "Week 9", "4 January 2027 / 28 December 2026"),
    ("Gate 4: release approval", "Week 13", "Week 12", "25 January 2027 / 18 January 2027"),
    ("Gate 5: production acceptance", "Week 17", "Week 15", "22 February 2027 / 8 February 2027"),
    ("Gate 6: closure after hyper care", "Week 22", "Week 20", "29 March 2027 / 15 March 2027"),
]

THREE = [
    ["1", "Access to the RPA logs to identify the failed cases", "Yes, for the baseline and the transition; no longer the agent's feed (now item 15).",
     "Read access to the RPA failure record (PurchaseOrder PDF table), the Power Automate flows and run history and the OCR model configuration (SOW 8.1(b)), the RPA's automation rate per customer cohort, with the owner at Accenture; the Existing RPA kept running as the fallback until Ingredion retires it (8.2(a)).",
     "The agent reads every case from the Salesforce queue for the cohorts moved to it. The logs give the baseline each cohort's completion rate is judged against, the backtest sample, the shadow-mode comparison and the fallback when a cohort is moved back."],
    ["2", "Current schema used by the Existing RPA to build the SAP payload", "Yes. Step A8 builds the same payload; A9 writes it (now item 10).",
     "The order creation method Ingredion approves at Gate 2 (current option: SAP Order API or BAPI via APIM, SOW 2.3), its specification, the RPA's field mapping and the SAP field requirements (8.1(c)), 10 to 20 sample payloads of created orders with their SAP numbers, and the interface that reads the SAP incompletion log (2.5).",
     "Payload parity avoids new SAP rejections; the samples are the test oracle before non-production SAP exists; the incompletion log feeds the follow-ups A10 writes to the case."],
    ["3", "Access to Salesforce to view cases", "Yes, as an API, and wider than viewing (now items 12 and 13).",
     "An API user or connected app with read on the Salesforce queue and the cases (email body, attachments), the permissions and access scope to read and update cases (8.1(b)), the field and status catalogue, a sandbox; plus the Salesforce-side routing of email order cases to the agent by cohort, agreed at Gate 2 (2.3, 8.1(e)), and the claim, outcome and follow-up fields the agent writes.",
     "A1 and A10 are the agent's entry and exit; cohort routing is how cut-over and fall-back work; Parkar does not configure Salesforce (10.3)."],
]

FULL = [
    ("1", "Named sponsor, technical lead and use-case lead who decide within 5 working days; the Ingredion Project Manager named before signature; attendance at the weekly status meeting and the 4-weekly steering review", "Gate decisions; scope, design and transition decisions; single point of contact", "Sponsor", "Before 26 October (week 0)", "SOW 8.1(a), 8.2(c), 9.0"),
    ("2", "Subject-matter experts for SAP, Salesforce, the Existing RPA, infrastructure and security, and the Google Cloud platform team (our ask: about 5 hours a week each)", "Walkthroughs; interface confirmation; UAT scenarios", "Technical lead", "Week 0 onward", "SOW 8.1(a)"),
    ("3", "Third parties engaged through Ingredion: Accenture (Existing RPA, SIEM), NTT Data, Infosys, and the Google Cloud platform team", "RPA logs and transition; SAP reads; project set-up; they attend walkthroughs and answer access requests", "Technical lead", "Week 0", "SOW 8.1(a); Appendix 2"),
    ("4", "Named UAT users and reviewers per cohort, and the test-case format Ingredion will expand into its SIT and UAT cases (A-D16b)", "Assisted mode (every case in Phase 1); UAT sign-off within 5 working days", "Use-case lead", "Reviewers by Gate 2 (week 5)", "SOW 8.1(e), 2.6"),
    ("5", "Historical sample of 500 past email POs including RPA-failed POs, representing the order and failure mix: PO emails with attachments, RPA and OCR output, failure reasons and the final SAP orders; confirmation that the orders are correct", "The Stage 1 backtest for a primary processor (A-D5); the Stage 1 clock starts when it is in place", "Use-case lead", "Within 5 working days of 26 October", "SOW 8.1(c), 8.2(b), 2.5"),
    ("6", "Failure analysis for 1 June to 31 July 2026 (1,180 records, 133 Customers; received 23 October as NA NoTouch Error Analysis - ShipTo.xlsx), the agreed baseline period, and the Existing RPA's automation rate per customer cohort: still needed is the full population of about 4,000 cases for the period, by customer and ship-to, with the outcome of each", "The baseline (A-D1); the completion-rate threshold set at Gate 1 (2.7); cohort order", "Use-case lead", "Week 0 (population still open)", "SOW 2.2, 2.5, 2.7"),
    ("7", "Current handling time per case and monthly volumes per cohort", "Business case (A-D6); the handling-time measure in the scorecard (2.7); reviewer capacity per cohort", "Use-case lead", "Week 2", "SOW 2.5, 2.7"),
    ("8", "Recordings of problem cases, existing documentation and prior analysis, the SAP field requirements for order creation, the SAP field mapping and the pricing and contract sources to compare against", "Process review (A-D1); payload specification (A8); price checks (A5)", "Use-case lead", "Week 0", "SOW 8.1(c)"),
    ("9", "SAP read interfaces, or the Google Cloud data sources that already hold the SAP data (2.5): master data for customer, ship-to, bill-to and material, CMIR, unit-of-measure conversions, pricing, contract, availability (ATP, allocation, restricted products, volume commitments), existing orders; the order field that carries the customer PO number", "A4 maps directly to SAP fields (no mapping database); A5 checks; the lookup before any retry at A9; the validation location decision at Gate 1", "SAP team", "Week 1; confirmed in Stage 1", "SOW 2.4, 2.5, 8.1(b)"),
    ("10", "SAP order creation by the method approved at Gate 2 (current option: SAP Order API or BAPI via APIM): specification, the RPA's field mapping, sample payloads, test endpoint, service identity, and the interface that reads the SAP incompletion log for created orders", "A8 payload parity; A9 write and incompletion log; A10 follow-ups", "SAP and integration team", "Stage 2 (Gate 2, week 5)", "SOW 2.3, 2.4, 8.1(b)"),
    ("11", "Non-production SAP and Salesforce with test data and test users: representative master, pricing, contract and ATP data and the ability to create test orders safely", "Build tests (Stage 3); SIT and UAT (Stage 4)", "SAP and Salesforce teams", "Gate 2; Test project by Stage 4", "SOW 8.1(b), 5.2; Appendix 2"),
    ("12", "Salesforce API access: the queue and cases (email body, attachments) for the cohorts moved to the agent; the permissions and access scope to read and update cases; field and status catalogue; sandbox", "A1 pick-up; A10 case update", "Salesforce team", "Week 1", "SOW 8.1(b), 2.3"),
    ("13", "Salesforce-side change: routing of email order cases to the agent instead of the RPA bot queue, by Customer or mailbox cohort as agreed at Gate 2, so that no case is processed by both; the claim status, outcome marker and follow-up fields the agent writes; the cohort list and order", "Cut-over and fall-back per cohort; one-case-once control", "Salesforce team and use-case lead", "Gate 2, with dates per cohort", "SOW 2.3, 8.1(e), 8.2(a)"),
    ("14", "Microsoft Graph permissions on the shared order mailboxes for a service identity: read, and create drafts; no send permission (the reviewer sends the clarification email)", "A6 saves the clarification draft the reviewer sends", "Microsoft 365 team", "Stage 2", "SOW 8.1(b), 10.2"),
    ("15", "RPA failure record, Power Automate flows and run history, and the OCR model configuration (read); Accenture engaged; the Existing RPA kept running as the fallback until Ingredion retires it", "Baseline and transition; shadow-mode comparison (A-D22); fallback when a cohort is moved back", "Accenture via the technical lead", "Week 0", "SOW 8.1(b), 8.2(a), 10.2"),
    ("16", "Three Google Cloud projects in the Ingredion GCP environment, one per environment (Dev, Test, Prod), serving both agents, with billing, connectivity, deployment permissions and APIs enabled: Vertex AI with the approved Gemini models and quota, Document AI, Model Armor, Cloud Run, Cloud Storage, Secret Manager, Cloud Trace, Cloud Logging, Cloud Monitoring, Artifact Registry", "Stage 1 prototype (Dev); Stage 3 build and pipelines (Test, Prod)", "Google Cloud platform team", "Dev in week 0; Test and Prod in Stage 3", "SOW 5.0, 8.1(b); Appendix 2"),
    ("17", "One dedicated service account per agent and environment with least-privilege IAM (approved at Gate 2, tested under 5.4); Workload Identity for the pipeline; region decision", "Every integration and every model call; the authorization tests in 5.4", "Cloud platform and security", "Week 0", "SOW 2.3, 5.4"),
    ("18", "Connectivity from the Google Cloud projects to the SAP gateway on Azure API Management, to Salesforce and to Microsoft Graph (private connectivity or allow-listed egress with mTLS or OAuth)", "A1, A4, A5, A6, A9, A10", "Network and security", "Decision week 0; path by week 2", "SOW 8.1(b) (connectivity); redline v2"),
    ("19", "One repository per agent in Ingredion's enterprise Git platform (GitHub, Bitbucket, Git or Azure DevOps) with access for the Parkar team and permission to configure the pipelines to Cloud Run; all code, prompts, rules, configuration and infrastructure-as-code live there and nowhere else", "From day one; Parkar holds no code outside it (5.1, 1.7)", "Technical lead", "Week 0", "SOW 5.1, 8.1(b), 1.7"),
    ("20", "Classification of PO, pricing and Customer data and approval of its use with AI models in the Ingredion GCP environment, with the approved model list, the region and the data-use terms; VPC Service Controls and customer-managed keys decisions", "Any model call on real POs, including the backtest", "Security and technical lead", "Week 0 (approval); Stage 2 (perimeter)", "SOW 8.1(d), 8.2(b)"),
    ("21", "Model Armor template defined and owned by Ingredion (prompt and response screening, with the Vertex AI safety filters)", "Guardrail before every model call; the prompt-injection tests in 5.4", "Security", "Stage 1", "SOW 2.3, 5.4"),
    ("22", "Security and architecture review of the Stage 1 prototype environment within 5 working days of the request; review of the design in time for Gate 2", "Gate 1 and Gate 2", "Security", "Week 2; Gate 2", "SOW 8.1(d), 4.2"),
    ("23", "Retention, archive, legal-hold and disposal policy per record category (source documents, extracted data, model outputs, reviewer actions, operational logs), confirmed in Stage 2; approval of the historical data used in Dev and Test, unmasked", "Audit store and retention design in A-D9, approved at Gate 2 and demonstrated in Stage 4; realistic test data", "Records management, legal and security", "Stage 2", "SOW 5.3, 5.2"),
    ("24", "Walkthroughs: current flow, Customer Service triage rules, the cohorts and their Customers, today's handling of multi-PO emails and Canadian orders", "A2 classification; cohort order; scope", "Use-case lead and SMEs", "Week 1", "SOW 2.5, 8.1(c)"),
    ("25", "User IDs and access in week 0 (later requests within 5 working days); workspace, badge and network access at Westchester, IL; secure remote access for the Pune team; a shared Teams channel", "Onsite Forward Deployed Engineer and Business Analyst; the offshore team", "Facilities and IT", "Week 0", "SOW 8.1(b), 8.2(c), 11.4"),
    ("26", "The secure-coding standard, the approved static-analysis, dependency and secrets-scanning tools, the vulnerability severity definitions and the scope of Ingredion's security review; permission to run the scanners in the pipeline", "The 5.4 testing from the first Stage 3 build; critical and high findings closed before Gate 4", "Security", "Gate 2 (week 5)", "SOW 5.4, 8.1(d), 4.2"),
    ("27", "The run owner and the AMS partner named, with monitoring ownership, alert routing and the escalation path for the run model (A-D20); the AMS partner available for the Knowledge Transition sessions and reverse shadowing in weeks 18 to 21", "Gate 4 needs the agreed run model; Gate 6 needs the AMS partner's sign-off", "Sponsor and technical lead", "Run model by Gate 4 (week 13); KT plan by end of Stage 5", "SOW 1.5, 2.5 (Stage 6), 8.1(e), 4.2"),
    ("28", "Post-creation evidence for the scorecard: the change history of orders the agent created and the manual corrections made after creation, so undetected errors and handling time can be reported from assisted mode onward", "Scorecard and reporting (2.7): A-D23, A-D24, A-D26", "SAP team and use-case lead", "Gate 2", "SOW 2.7"),
]
FULL_BANDS = {0: "People and decisions", 4: "Data for the Stage 1 backtest", 8: "SAP", 11: "Salesforce and Outlook", 14: "Existing RPA (transition)", 15: "Google Cloud platform", 19: "Security and approvals", 23: "Process knowledge and logistics", 25: "Added for SOW No. 07 (sections 5.4, 1.5 and 2.7)"}

AGENT_B = [
    ("B1", "Sample of past invoiced orders, in the number agreed in week 0, representing the mix of gaps and including the anchor case (Kraft Heinz sales order 809-6862): the Customer PO, the SAP order, delivery and billing data, and the dispute or payment outcome; the correct outcome confirmed for each test case", "B-D2 test cases and the Stage 1 backtest (B-D5); the Agent B Stage 1 clock", "Agent B use-case lead; Pricing and Billing", "Within 5 working days of 26 October", "SOW 8.1(c), 8.2(b), 3.6"),
    ("B2", "Read access, or a scheduled data extract where no read interface exists: SAP order, delivery, billing, pricing and freight data; PROS price records; Salesforce cases and PO documents; Customer POs held in Ariba; TermSync; the contract and fuel-rate files", "B2 evidence assembly; read-only, least privilege", "Technical lead; system owners", "Week 0 to week 1", "SOW 8.1(b), 3.5; Appendix 2"),
    ("B3", "The invoice-ready signal: how an invoice-ready order is defined and identified in SAP, and read access to it; the candidate confirmed in Stage 1, the definition agreed in Stage 2", "B1 pick-up; the scope boundary of the agent", "SAP team; Pricing and Billing", "Candidate in Stage 1; agreed by Gate 2", "SOW 8.1(b), 8.2(a), 3.6"),
    ("B4", "Business rules: the variance for each check, the rule for which source wins, the portal rules of the Customers in scope, the source of the freight and fuel rates; unit-of-measure and currency conversion rules", "B4 and B5 rules; confirmed at Gate 1, fixed in B-D8 at Gate 2", "Pricing and Billing; Commercial", "Stage 1 (Gate 1)", "SOW 8.1(c), 8.2(a), 3.3"),
    ("B5", "A named owner for each outcome and each human step (Customer Service or Commercial for Updated PO required; CBA, Sales and PROS owners for price corrections); the identities and the notification channel for the review queue", "B7 routing; the human judgment gate", "Sponsor; Agent B use-case lead", "Owners in Stage 1; queue users by Gate 2", "SOW 8.1(a), 8.1(b), 3.3"),
    ("B6", "Subject-matter experts in Pricing and Billing, AR and Collections, Customer Service, SAP, PROS, Salesforce, infrastructure and security", "Walkthroughs; rule confirmation; UAT", "Technical lead", "Week 0 onward", "SOW 8.1(a)"),
    ("B7", "The root-cause analysis of 6 August 2026 (26,860 open or late invoices; 3,155 pricing discrepancy; 674 freight bill disputed), the solution brief of 7 October 2026 and the dispute volumes by type", "B-D1 baseline; the preventable share measured in Stage 1", "Agent B use-case lead", "Week 0", "SOW 3.2, 8.1(c)"),
    ("B8", "Ingredion-side changes so the agent receives invoice-ready orders and reads the sources, by the Gate 2 dates; non-production source systems or data extracts with test data and test users", "Stage 3 build; Stage 4 SIT", "Technical lead; system owners", "Gate 2 (dates); Stage 3", "SOW 8.1(e), 8.1(b)"),
]

WEEK0 = [
    "SOW No. 07 signed; the Ingredion Project Manager named; Appendix 3 staffing supplied by Parkar (item 1)",
    "Named sponsor, technical lead and use-case leads for both agents (item 1)",
    "Accenture, NTT Data, Infosys and the Google Cloud platform team engaged (items 3, 15)",
    "Historical sample of 500 POs with the final SAP orders, within 5 working days of 26 October (item 5); the Agent B sample of past orders in the same window (B1)",
    "Failure analysis for June to July 2026, baseline period and the RPA automation rate per cohort (item 6)",
    "Google Cloud Dev project with Vertex AI (approved Gemini models, quota), Document AI, Model Armor, Cloud Run, Secret Manager and Cloud Trace enabled, for both agents (item 16)",
    "Dedicated service accounts with least-privilege IAM; region decided (item 17)",
    "Connectivity approach decided: Google Cloud projects to SAP API Management, Salesforce and Graph (item 18)",
    "One repository per agent in Ingredion's Git platform with pipeline permissions (item 19)",
    "PO, pricing and Customer data classified and approved for use with Vertex AI; approved model list (item 20)",
    "User IDs, onsite access at Westchester, remote access and a shared Teams channel (item 25)",
]

DECISIONS = [
    ("SOW No. 07 signature, before 26 October", "The redline is now the contract text: both agents from week 0, a fixed fee per agent, 5-working-day review periods, and scope and fees not reopened at Gate 1 (8.2(c)). Parkar supplies Appendix 3 (roles, committed capacity, named key persons, FTE by week); Ingredion names its Project Manager.", "Start date, team, the Stage 1 clock"),
    ("Pre-existing materials, before Stage 3", "Parkar must identify in writing any generic tools, libraries and know-how it brings (the shared factory runtime, open-source components) before incorporating them; Ingredion approves, and licences are listed in A-D16a (1.7). All Agent Work Product lives in Ingredion's repository only (5.1).", "What we reuse from our runtime; the repository set-up in week 0"),
    ("Transition routing, Gate 2", "Email order cases move from the RPA bot queue to the agent by Customer or mailbox cohort, as agreed at Gate 2 (2.3), so that no case is processed by both; the first cohorts, the shadow duration and reviewer capacity are sized in Stage 1.", "Rollout plan, reviewer staffing, Gate 5 criteria"),
    ("Connectivity approach, week 0", "Private connectivity to the Azure network or allow-listed egress with mTLS or OAuth to API Management; the same decision covers Salesforce and Graph. The SOW lists connectivity with the GCP projects (8.1(b)) without naming the method.", "Items 9, 10, 12, 14, 18"),
    ("Validation location, Gate 1", "Whether the checks run against SAP interfaces or against the SAP data already available in Google Cloud (2.5); Parkar recommends in Stage 1, Ingredion decides at Gate 1 (4.2).", "A4 design and the SAP reads"),
    ("SAP method, Gate 2", "SAP Order API or BAPI via APIM (2.3), and with it the idempotency approach for the write.", "A9, item 10"),
    ("Google Cloud services, Stage 2", "The redline's services are confirmed in Stage 2 (3.3, A-D11), including the review queue app, the audit store technology and the region.", "Environment design (A-D11)"),
    ("Data approval for Vertex AI, week 0", "The approval must cover PO, pricing and Customer data and name the models, the region and the data-use terms (8.1(d)); VPC Service Controls and keys are decided in Stage 2.", "Item 20; the start of the backtest"),
    ("Retention policy, Stage 2", "Retention, archive, legal hold and disposal per record category are Ingredion policies, confirmed in Stage 2 and built into A-D9 (5.3).", "Audit store design; item 23"),
    ("Multi-PO emails, Gate 2", "An email with more than one PO is processed as separate orders (2.4); how N orders sit on one Salesforce case, including partial success, is fixed in the Stage 2 design.", "A2 splitting, A10 case update, reporting"),
    ("Canada, Stage 1", "Agent A covers North America (1.6); confirm whether Canadian cases share the mailboxes, Salesforce routing, RPA and SAP set-up. Non-English POs stay out of scope (8.2(b)).", "Scope and volumes"),
    ("Phase 2 criteria, Gate 5", "Which high-confidence cases may be created in SAP without reviewer confirmation is an Ingredion decision at Gate 5 (4.2); configuring it afterwards is change control (2.4).", "The review policy after Gate 5"),
]

WHY_WEEK0 = [
    ("1", "Named leads and Project Manager", "The SOW gives Ingredion 5 working days for decisions, deliverable reviews and gate decisions (8.1(a), 4.2); issues unresolved after 5 working days escalate to the sponsor and Parkar's engagement lead (9.0); the Project Manager is the single point of contact (8.2(c)).", "No owner for decisions; the plan moves day for day (8.2(c))."),
    ("3", "Third parties and the platform team", "Accenture runs the Existing RPA and the SIEM; Infosys and NTT Data sit on the SAP and infrastructure side; the platform team creates the projects, enables the APIs and grants IAM. Ingredion manages all three providers (8.1(a)); items 9, 10, 15 and 16 come from them.", "The projects, the reads and the RPA data do not arrive."),
    ("5", "Historical sample of 500 POs", "The backtest (A-D5) runs on 500 past email POs including RPA-failed POs, scored field by field against the SAP orders finally created (2.5, 8.2(b)); confirmation that those orders are correct (8.1(c)) makes the numbers defensible. Stage 1's three weeks count from the day access and the sample are both in place (8.2(c)).", "The Stage 1 clock does not start; Gate 1 is judged on the wrong population."),
    ("6", "Failure analysis, baseline period, RPA rate per cohort", "Completion rate per cohort against the RPA's rate on the same cohort is the headline measure; the scorecard thresholds (2.7) are set at Gate 1 from the backtest; the sample is drawn from the agreed period (1 June to 31 July 2026).", "No baseline, no cohort order, no business case."),
    ("16", "Google Cloud Dev project with the APIs enabled", "Each environment is its own GCP project and both agents run in it (5.0, 8.1(b)); Vertex AI serves A2, A3 and A6; Document AI reads scans in A3; Model Armor screens text before every model call; Cloud Run is the runtime; Secret Manager and Cloud Trace carry credentials and traces. Dev is needed from Stage 1.", "No prototype in the project means no backtest on real POs."),
    ("17", "Dedicated service account, IAM, region", "Every read and every model call runs as this identity; write roles are granted only for A6, A9 and A10; the 5.4 authorization tests prove it has only the access approved at Gate 2; the region fixes where Gemini, Document AI and Model Armor run.", "The write boundary becomes a convention; an undecided region blocks the data approval."),
    ("18", "Connectivity approach", "The agent runs on Google Cloud; SAP is behind Azure API Management, Salesforce is SaaS, drafts go through Microsoft Graph. Private connectivity or allow-listed egress with mTLS or OAuth must be decided before anything is built; the SOW names connectivity among what Ingredion provides with the projects (8.1(b)).", "Everything is granted but unreachable; network changes take weeks and involve three parties."),
    ("19", "Repository on Ingredion's Git platform", "All code, prompts, rules, configuration and infrastructure-as-code are stored in Ingredion's repository and nowhere else (5.1, 1.7); the pipeline deploys from it to Dev, Test and Prod; one repository per agent (8.1(b)).", "A late repository forces code to exist outside the client's control, which the SOW forbids."),
    ("20", "Data approval for Vertex AI", "Ingredion classifies PO, pricing and Customer data, approves its use with AI models in the GCP environment and lists the approved models (8.1(d)); until then not one real PO can be sent to Gemini.", "The backtest cannot start, whatever else is ready."),
    ("25", "User IDs, onsite access, remote access, Teams channel", "Two roles are onsite at Westchester 2 to 3 days a week; six offshore people in Pune for Agent A and five for Agent B (1.6, 8.2(c), 11.4); access requests after week 0 take up to 5 working days (8.1(b)).", "The onsite roles cannot start; the offshore team has no path to the client's systems."),
]

WHY_WEEKS12 = [
    ("2", "Subject-matter experts", "SAP, Salesforce, Existing RPA, infrastructure and security (8.1(a)), plus the Google Cloud platform team; they confirm the interfaces and explain the cohorts.", "The exception map (A-D2) and the integration design are guesses."),
    ("7", "Handling time and volumes per cohort", "The business case (A-D6), the handling-time measure in the scorecard (2.7) and the reviewer capacity each cohort needs in Phase 1.", "Completion numbers but no value number and no staffing plan."),
    ("8", "Recordings, documentation, SAP field requirements", "The recordings are the fastest route to the exception map; the SAP field requirements, field mapping and pricing and contract sources (8.1(c)) define what A8 must fill and what A5 compares against.", "Stage 1 rediscovers what Ingredion already knows."),
    ("9", "SAP read interfaces or Google Cloud data sources", "A4 maps directly to SAP fields and converts units with SAP's own data (no mapping database); A5 reads pricing, contract and availability and checks duplicates; A9 looks an order up before any retry, which needs the order field that carries the customer PO number. The SOW notes the SAP data is already available in GCP (2.5), so the sources are confirmed with the validation location decision.", "A4 cannot validate; the duplicate controls do not exist; price flags cannot be computed."),
    ("12", "Salesforce API access", "A1 reads the queue and the email; A10 writes the result; Ingredion confirms the permissions and access scope (8.1(b)).", "The agent has no intake and no exit."),
    ("15", "RPA failure record, flows, OCR configuration, Accenture engaged", "Baseline and transition; the shadow-mode report compares the agent with the RPA's orders (A-D22); the RPA kept running as fallback until Ingredion retires it (8.2(a), 10.2).", "No baseline per cohort; no shadow-mode comparison; no rehearsed fallback."),
    ("21", "Model Armor template", "Screens email and PO text before every model call (2.3); the template, its filters and confidence levels are Ingredion's; it fails closed; the 5.4 prompt-injection tests run against it before each release.", "Real POs parked for review, or document text can steer the model."),
    ("22", "Security review slots", "Ingredion reviews the prototype environment within 5 working days of the request (8.1(d)) and the design in time for Gate 2; Gate 2 cannot pass without the architecture and security review (4.2).", "The review lands in week 3 and competes with the executive readout, or Gate 2 slips."),
    ("24", "Walkthroughs, triage rules, cohorts", "A2 classification, the cohort order, multi-PO handling and Canada scope (2.5).", "The first cohort is chosen blind."),
]

WHY_GATE2 = [
    ("4", "UAT users and reviewers per cohort; test-case format", "Every case stops at a reviewer in Phase 1; reviewers learn the queue app through UAT and sign it off within 5 working days (8.1(e)); the baseline test cases (A-D16b) must arrive in a form Ingredion can expand.", "Reviewers meet the queue for the first time in production."),
    ("10", "SAP order creation method and incompletion log", "Approved at Gate 2 (SAP Order API or BAPI via APIM, 2.3); the method decides how exactly-once is enforced and how the incompletion log is read (2.4).", "A9 is built against the wrong interface; a timeout after creation can create a second order."),
    ("11", "Non-production SAP and Salesforce", "Build tests and SIT create real test orders; the systems need representative master, pricing, contract and ATP data and test users (8.1(b)).", "Tests pass against stubs and fail in production."),
    ("13", "Salesforce routing by cohort, claim and outcome fields", "Cut-over and fall-back are routing changes agreed at Gate 2 (2.3) and made by Ingredion by the Gate 2 dates (8.1(e)); the claim status keeps the RPA and manual staff off a case the agent holds.", "Two actors can work one case; no cohort can be moved safely."),
    ("14", "Microsoft Graph permissions, drafts only", "A6 saves the clarification as a draft in the shared mailbox; only the reviewer sends it (10.2). A send permission would let the agent email a customer, which the design forbids.", "Drafts cannot be saved, or the permission is too broad for the security review."),
    ("16", "Test and Prod projects", "Built the same way as Dev so a release moves through the pipeline unchanged (5.0); provided in Stage 3 (Appendix 2); Test for Stage 4, Prod for shadow mode.", "Stage 4 cannot start on time."),
    ("20", "VPC Service Controls and key management", "The perimeter and customer-managed keys are security decisions for the production project.", "Production approval stalls at Gate 4."),
    ("23", "Retention policy; unmasked historical data", "Retention, archive, legal hold and disposal per record category are Ingredion policies confirmed in Stage 2, documented in A-D9 and demonstrated in Stage 4 (5.3); Dev and Test run on approved historical data (5.2), and masked POs weaken extraction testing.", "No retention target at Gate 2; masked test data hides real failures."),
    ("26", "Secure-coding standard, scanning tools, severity definitions", "Parkar must run static analysis against an agreed secure-coding standard, secrets scanning, dependency scanning on every build, authorization tests, prompt-injection tests and a rehearsed rollback (5.4), and close critical and high findings before Gate 4 (4.2). The standard, the tools and the severity scale are Ingredion's.", "Findings are argued about instead of fixed; Gate 4 slips."),
    ("28", "Post-creation evidence for the scorecard", "Undetected errors are errors in created orders that neither the agent nor the reviewer caught (2.7); from assisted mode they can only be measured from what happens to the order afterwards (change history, manual corrections).", "The scorecard reports a number nobody can verify."),
]

WHY_GATE4 = [
    ("27", "Run owner and AMS partner", "The release readiness pack (A-D20) must contain a run model agreed with Ingredion: operating owner, monitoring ownership and alert routing, severity definitions and escalation path, hand-off to warranty and to the AMS partner (1.5). In Stage 6 the AMS partner operates the agent with Parkar support (reverse shadowing) and signs off the Knowledge Transition at Gate 6 (2.5, 4.2).", "Gate 4 cannot pass; Gate 6 has no one to accept the handover."),
]

REFS = [
    ("1.3 / 7.0", "Project duration; project plan", "Start 26 October 2026 (week 0); Agent A Gate 5 in week 17 and Gate 6 in week 22; Agent B Gate 5 in week 15 and Gate 6 in week 20; Stage 1 counts from access and sample in place"),
    ("1.5", "Service levels, warranty and run model", "90-day warranty after Gate 6; incident severities; the run model agreed before Gate 4 in A-D20, including the hand-off to the AMS partner"),
    ("1.6", "Engagement summary", "Both agents side by side: role, first release, production mode, team (six offshore people for Agent A, five for Agent B, two shared onsite roles), region"),
    ("1.7", "Ownership and intellectual property", "Agent Work Product owned by Ingredion; pre-existing materials identified in writing and approved before use; no code held outside Ingredion's repository; no training on Ingredion data"),
    ("2.2 / 2.3", "Agent A current and proposed process", "The RPA's ten steps and failure counts; the agent's ten steps A1 to A10 on Google Cloud, the human judgment gate, exits to the manual queue, the transition from the Existing RPA by cohort agreed at Gate 2"),
    ("2.4 / 2.5", "Solution to be delivered; activities by stage", "All email orders; input formats; master-data, price, contract, availability and duplicate checks; incompletion log; Stage 1 interface confirmation and the validation location decision; Stage 6 Knowledge Transition"),
    ("2.6 / 2.7", "Deliverables; success measures and reporting", "A-D1 to A-D26 (including A-D16a to c); the scorecard (completion rate, field-level accuracy, undetected errors, reviewer confirmation, handling time, run cost) and the reporting list from Stage 5"),
    ("3.2 to 3.7", "Agent B", "Current flow and anchor case; eight steps B1 to B8; four checks, three outcomes, variances; scorecard; deliverables B-D1 to B-D26"),
    ("4.1 / 4.2", "Stages, gates and acceptance", "Durations per agent; 5 working days to review a deliverable or give a gate decision; silence is acceptance; gate criteria, including 5.4 closure before Gate 4"),
    ("5.0 to 5.2", "Environments; source control", "One GCP project per environment; Ingredion's Git platform as the single source of truth; Dev and Test on approved historical data; only Prod handles live cases"),
    ("5.3", "Data retention", "Retention, archive, legal hold and disposal per record category, confirmed by Ingredion in Stage 2, built by Parkar and demonstrated in Stage 4"),
    ("5.4", "Security and production-readiness testing", "Secure code, dependency scans, authorization tests, prompt-injection tests, rehearsed rollback, production-readiness checklist; critical and high findings closed before Gate 4"),
    ("8.1(a) to (e)", "Ingredion's responsibilities", "(a) people and decisions, (b) access and environments, (c) data and documentation, (d) security and approvals, (e) build, test and production; the 5-working-day periods"),
    ("8.2(a) to (c)", "Assumptions", "Scope and approach; data and technology (500 POs, English only, GCP); delivery and timeline (Stage 1 clock, dependency attribution, key persons, delays move the plan day for day)"),
    ("9.0 / 10.x", "Governance; out of scope", "Weekly status, 4-weekly steering, RAID log, escalation; no work inside SAP, Salesforce, PROS, Ariba or TermSync; no SIEM or SAP AI connection; licences and cloud costs are Ingredion's"),
    ("Appendix 2 / 3", "RACI; staffing plan", "Who is accountable for each week-0 and Stage 1 activity; Parkar's roles, committed capacity and key persons, due before signature"),
    ("Redline v2", "Ingredion's three diagrams of 20 October 2026", "Agent A on Google Cloud; Agent B architecture and PO alignment flow; reproduced in SOW sections 2.3 and 3.3"),
    ("Item N", "Parkar's responses to the clarification questions", "Written against Draft 3.0; still the source for the Salesforce, price and unit-of-measure detail"),
]


def why_table(rows):
    return table(["#", "Requirement", "Why the agent or the plan needs it", "What breaks without it"], [list(r) for r in rows], [8 * mm, 36 * mm, 80 * mm, CONTENT_W - 124 * mm])


def build() -> None:
    doc = Doc(str(OUT))
    story: list = [
        Spacer(1, 38 * mm),
        P("INGREDION AGENTIC AI FACTORY · EMAIL ORDER INTAKE AGENT · SOW NO. 07", "kicker"),
        P(TITLE, "title"),
        Spacer(1, 6 * mm),
        P("Access, data and decisions needed from Ingredion before Stage 1 can start on Google Cloud, with the reason behind each item and where it sits in the redlined SOW No. 07; the Pre-bill Agent's items for the same weeks are listed too.", "subtitle"),
        Spacer(1, 28 * mm),
        P(f"<b>Prepared by</b> {AUTHOR}, {ORG}", "body"),
        P(f"<b>Date</b> {DATE} · <b>Version</b> {VERSION} · <b>Status</b> for internal review", "body"),
        P("<b>Basis</b> Ingredion's redline v2 of Statement of Work No. 07 (20 October 2026) and its three diagrams; Parkar's responses to Ingredion's clarification questions", "body"),
        Spacer(1, 40 * mm),
        P("Tick the boxes as items are confirmed; this file keeps the ticks when saved from a PDF reader.", "small"),
        NextPageTemplate("Body"),
        PageBreak(),
    ]
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    toc.dotsMinLevel = 0
    story += [P("Contents", "h1"), toc, PageBreak()]
    story += [
        Heading("1. Summary"),
        P("This list is written against Ingredion's redline v2 of Statement of Work No. 07 (20 October 2026), which covers both agents of the Agentic AI Factory under one contract. The SOW commences on 26 October 2026 with both agents in week 0. Agent A runs 18 weeks to production acceptance at Gate 5 (week 17), with hyper care in weeks 18 to 21 and closure at Gate 6 in week 22; Agent B runs 16 weeks to Gate 5 (week 15) and closes at Gate 6 in week 20. Both run on Google Cloud in the Ingredion GCP environment, and Agent A processes all email order cases in place of the Existing RPA."),
        P("All three items originally listed are still needed, in a more specific form: the RPA logs for the baseline and the transition, the SAP payload schema for the order write, and Salesforce access for the case queue the agent now reads directly. Beyond them, 28 items in nine areas are needed for Agent A, eight items for Agent B fall due in the same weeks, and twelve decisions sit with Ingredion. Eleven items block the start of Stage 1."),
        P("What the SOW changed since the earlier list: every turnaround is now 5 working days (decisions, deliverable reviews, gate decisions, access requests, the prototype security review, UAT sign-off and production approval), and the historical sample is due within 5 working days of the start; the three environments are three GCP projects shared by both agents; data retention (5.3) and security and production-readiness testing (5.4) are new sections that need client inputs; Stage 6 adds a Knowledge Transition to Ingredion's AMS partner, with a run model agreed before Gate 4; and the intellectual-property clause (1.7) requires Parkar to declare any pre-existing materials before using them and to hold no code outside Ingredion's repository. The Stage 1 clock starts only when access and the sample are both in place (8.2(c)); connectivity from the Google Cloud projects to the SAP gateway on Azure remains the item most likely to slip."),
        Heading("1.1 Gate calendar", 1),
        P("Weeks are counted from the week of 26 October 2026 (Appendix 1). The dates hold only if the week-0 items land, because Stage 1's three weeks count from the day access and the sample are both in place."),
        table(["Milestone", "Agent A", "Agent B", "Week starting (Agent A / Agent B)"], [list(r) for r in CALENDAR], [52 * mm, 22 * mm, 22 * mm, CONTENT_W - 96 * mm]),
        Heading("2. The three items already listed, checked"),
        table(["#", "Item as listed", "Needed?", "Ask for exactly this", "Why we need it"], THREE, [7 * mm, 30 * mm, 28 * mm, 60 * mm, CONTENT_W - 125 * mm]),
        Heading("3. Full requirement list by area"),
        P("28 items. \"Needed by\" follows the SOW plan: week 0 is mobilisation, Stage 1 is weeks 1 to 3, Gate 2 is week 5, Gate 4 is week 13. Items 1, 2 and 3 above appear here as 15, 10 and 12 to 13; items 26 to 28 are new in SOW No. 07. Tick an item once Ingredion has confirmed it."),
        table(["", "#", "Requirement", "Why we need it", "Ingredion owner", "Needed by", "Ref"], [[Checkbox(), *r] for r in FULL], [6 * mm, 7 * mm, 56 * mm, 40 * mm, 25 * mm, 22 * mm, CONTENT_W - 156 * mm], bands=FULL_BANDS, checkbox_col=True),
        P("Reading the Ref column: numbers are sections of Statement of Work No. 07 as redlined by Ingredion on 20 October 2026 (8.1(a) to (e) are the five groups of Ingredion's responsibilities); \"Redline v2\" is Ingredion's set of three diagrams of the same date; \"item N\" is the numbered question in Parkar's responses. Section 8 gives the full key.", "small"),
        KeepTogether([
            Heading("4. Week-0 blockers"),
            P("Eleven items decide whether Stage 1 starts on day 1. Everything else can land in weeks 1 and 2 without moving Gate 1, provided the SAP reads (9), Salesforce API access (12) and the connectivity path (18) arrive by the end of week 2."),
            checklist(WEEK0),
        ]),
        Heading("5. Decisions we need from Ingredion"),
        P("These are decisions, not access. Each one changes the design or the plan, and each has a place in the SOW where it falls due."),
        table(["", "Decision and when", "Why it matters", "What it changes"], [[Checkbox(), f"<b>{a}</b>", b, c] for a, b, c in DECISIONS], [6 * mm, 40 * mm, 84 * mm, CONTENT_W - 130 * mm], checkbox_col=True),
        Heading("6. Pre-bill Agent: items due in the same weeks"),
        P("Agent B starts in the same week 0 and its Stage 1 clock also runs from access and sample in place. Items 1 to 3, 16, 19, 20 and 25 above already cover both agents (the GCP projects, one repository per agent and the data approval are shared); the eight items below are specific to Agent B and are drawn from SOW 8.1 and 3.6."),
        table(["", "#", "Requirement", "Why we need it", "Ingredion owner", "Needed by", "Ref"], [[Checkbox(), *r] for r in AGENT_B], [6 * mm, 7 * mm, 56 * mm, 40 * mm, 25 * mm, 22 * mm, CONTENT_W - 156 * mm], checkbox_col=True),
        Heading("7. Why each requirement"),
        P("Every requirement exists because a named agent step or SOW deliverable cannot run without it. The steps are the SOW's ten (section 2.3): A1 pick up the case from the Salesforce queue, A2 classify the email (Gemini), A3 read the PO (Gemini and Document AI), A4 map to SAP and validate, A5 rules and confidence, A6 exceptions (Gemini drafts the clarification, saved as an Outlook draft through Graph), A7 review summary, the human judgment gate, A8 build the SAP payload, A9 create the order (SAP write, then the incompletion log), A10 update the Salesforce case. A-D1 to A-D7 are the Stage 1 deliverables (2.6)."),
        Heading("7.1 Mandatory before week 0", 1),
        why_table(WHY_WEEK0),
        Heading("7.2 Weeks 1 to 2", 1),
        why_table(WHY_WEEKS12),
        Heading("7.3 By Gate 2", 1),
        why_table(WHY_GATE2),
        Heading("7.4 By Gate 4", 1),
        why_table(WHY_GATE4),
        Heading("8. Where the references point"),
        P("Section numbers are those of Statement of Work No. 07 (redline v2). The earlier list cited the scope sections of Draft 3.0 (5.1 to 5.5, 6.x, 7.2, 8, 9); those numbers no longer apply and have been re-keyed throughout.", "small"),
        table(["Reference", "Section", "What it covers"], [list(r) for r in REFS], [24 * mm, 50 * mm, CONTENT_W - 74 * mm]),
        KeepTogether([
            Heading("9. Sources"),
            P("Statement of Work No. 07, Ingredion Agentic AI Factory, Email Order Intake Agent and Pre-bill Validation and Dispute Prevention Agent, Ingredion redline v2 (redacted), 20 October 2026, 67 pages: sections 1.3 to 1.7, 2.2 to 2.7, 3.2 to 3.7, 4.1, 4.2, 5.0 to 5.4, 7.0, 8.1, 8.2, 9.0, 10.1 to 10.3, Appendices 1 to 3.", "small"),
            P("Ingredion redline v2 diagrams, 20 October 2026: Agent A proposed process and architecture on Google Cloud; Agent B future-state architecture and PO alignment flow.", "small"),
            P("Email Order Intake Agent, responses to Ingredion's SOW clarification questions: items 4, 5, 6, 7, 8, 11 and 12.", "small"),
            P("Ingredion Agent Workflows (companion document, revised 21 October 2026): the engineering review behind the connectivity, cohort and SAP-method points.", "small"),
        ]),
    ]
    doc.multiBuild(story, canvasmaker=NumberedCanvas)

    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=str(OUT))
    writer.add_metadata({"/Producer": ORG, "/Creator": f"{AUTHOR}, {ORG}", "/Author": AUTHOR, "/Title": TITLE})
    writer.page_mode = "/UseOutlines"
    with OUT.open("wb") as fh:
        writer.write(fh)


if __name__ == "__main__":
    build()
    print("written", OUT)
