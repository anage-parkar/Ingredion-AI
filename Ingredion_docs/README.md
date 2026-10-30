# Ingredion engagement — document index and extracted knowledge

Compiled 16 October 2026, revised 19 October after the AVP discussion confirmed two agents, and
revised again 21 October 2026 for **Ingredion's redline v2 (20 October 2026)**: the three diagrams and the
redlined **Statement of Work No. 07** (both agents under one SOW; in `redline-v2/`), which supersede
the Azure, fallback-only design below wherever they differ. Figures and dates are quoted from the
documents; anything marked *TBC* is still open in the source itself. The workflow page
`ingredion-agent-workflows.html` (published as a Claude artifact) and `Ingredion_Agent_Workflows.pdf`
draw both agents, the shared runtime and the engineering review as of redline v2. `ingredion-data-architecture.html` (26 October 2026) covers the data platform the agents sit on, and `ingredion-factory-and-gold-flow.html` (30 October 2026) explains what the `factory/` package is (governance, agent ops and runtime in one) and the code path from the BigQuery gold tables and the Cloud Storage files bucket into the agents, with inputs and outputs per connector method.

## 0. Redline v2 (20 October 2026) — what now governs the design

Three diagrams and the redlined SOW from Ingredion, stored in `redline-v2/`:

| File | What it shows |
|---|---|
| `redline-v2/agent-a-order-intake-google-cloud.png` | Agent A proposed process and architecture on Google Cloud: ten steps A1–A10, one human gate, Cloud Run / Vertex AI / Document AI / Model Armor / audit store, Google Cloud native observability |
| `redline-v2/agent-b-prebill-google-cloud.png` | Agent B future-state architecture on Google Cloud: six read-only sources, Cloud Run agent code, Gemini for B3 and B6, Model Armor, Cloud Storage extract landing, B7 review queue, B8 audit store, owners per outcome |
| `redline-v2/agent-b-po-alignment-flow.png` | Agent B eight-step PO alignment flow, four checks in the first release, three outcomes, the Kraft Heinz anchor |
| `redline-v2/Statement_of_Work_7_-_EMail_order_intake_and_pre-bill_validation_agents_INGR_REDLINE_v2_Redacted (1).pdf` | SOW No. 07, Ingredion redline v2 (67 pages, fees redacted): both agents under one SOW; sections 1.0 to 11.0 and Appendices 1 to 3 (terms, RACI, staffing-plan placeholder). Text pages are extractable; 39 pages are images |

What changes against the earlier documents:

- **Platform.** Both agents run in the Ingredion Google Cloud project (Dev, Test, Prod): Cloud Run for
  agent code, rules, connectors and the review queue app; an approved Gemini endpoint on Vertex AI;
  Document AI for scanned POs; Model Armor before every model call; Cloud Storage for scheduled extracts;
  an immutable audit store with retention per 5.3; Cloud Trace, Logging and Monitoring (OpenTelemetry);
  one dedicated service account, least-privilege IAM, Secret Manager. Services are confirmed in Stage 2.
- **Agent A scope.** Processes *all* email orders from Salesforce, cohort by cohort. Ingredion routes
  each customer cohort to the agent; the Existing RPA (Power Automate) keeps the cohorts not yet moved and
  stays as fallback until Ingredion retires it; Parkar does not change it. Every exit goes to the manual
  queue (Customer Service) with the agent's reason on the original Salesforce case.
- **Agent A steps (ten, generative AI in A2, A3, A6).** A1 pick up the case (Salesforce read) · A2 classify
  the email (new order, revised PO, duplicate or not an order; splits multi-PO emails) · A3 read the PO
  (PDF, scans, Excel, Word or email body; confidence per field) · A4 map to SAP and validate (direct to SAP
  fields; customer, ship-to, bill-to, material, CMIR, UOM; **no mapping database**) · A5 rules and
  confidence (price, contract, ATP, duplicate checks) · A6 exceptions (drafts the customer clarification
  for the reviewer; Graph) · A7 review summary · human gate (every case in Phase 1) · A8 build SAP payload
  · A9 create order (SAP order API / BAPI via APIM, method approved at Gate 2; then reads the SAP
  incompletion log) · A10 update the case (order number, status, audit note, incompletion follow-ups).
  Validation location (SAP or Google Cloud) recommended in Stage 1, decided at Gate 1. Phase 2
  (high-confidence cases skip the gate) is an Ingredion decision at Gate 5.
- **Agent B.** Same eight steps; **all four checks in the first release**; outcomes Matched · Updated PO
  required · Fix our side or decide; owners: nobody (Matched), Customer Service or Commercial (updated PO),
  the Ingredion owner (fix our side; price changes sit with CBA, Sales and PROS). Read access to Ariba and
  TermSync confirmed in Stage 1; read interface or scheduled extract per source.

**SOW No. 07 (redline v2) facts that fix the plan** (section numbers are the SOW's):

- **Dates.** Commences 26 October 2026 (week 0) for both agents (1.3, 7.0). Agent A: 18 weeks including
  week 0 to Gate 5 (week 17), hyper care weeks 18–21, Gate 6 in week 22. Agent B: 16 weeks to Gate 5
  (week 15), hyper care weeks 16–19, Gate 6 in week 20. Stage 1's three weeks count from the day access and
  the historical sample are both in place (8.2(c)). The pre-bill 10-week PoC calendar of the 7 October brief
  is superseded (7.0).
- **Turnarounds.** Ingredion has 5 working days for decisions (8.1(a)), deliverable reviews and gate
  decisions (4.2; silence is acceptance), later access requests, the prototype security review, UAT sign-off
  and production approval (8.1); the historical samples are due within 5 working days of the start (8.1(c));
  issues unresolved after 5 working days escalate and are decided within 3 (9.0).
- **Environments and code.** Dev, Test and Prod are each a GCP project in the Ingredion GCP environment,
  shared by both agents (5.0); Dev and Test run on approved historical data, only Prod handles live cases
  (5.2); all code, prompts, rules, configuration and infrastructure-as-code live only in Ingredion's Git
  platform, one repository per agent (5.1, 8.1(b)).
- **5.3 Data retention (new).** Retention, archive, legal hold and disposal per record category (source
  documents, extracted data, model outputs, reviewer actions, operational logs) under policies Ingredion
  confirms in Stage 2; documented in A-D9 / B-D9, approved at Gate 2, demonstrated in Stage 4; audit records
  immutable.
- **5.4 Security and production-readiness testing (new, Parkar's work).** Static analysis against an agreed
  secure-coding standard, secrets scanning, dependency scanning on every build, authorization tests (least
  privilege; Agent B writes nothing; Agent A writes only through the approved methods after reviewer
  approval), adversarial prompt-injection tests before each release, a rehearsed rollback in Test before
  Gate 4, a production-readiness checklist; critical and high findings closed before Gate 4, medium before
  Gate 5 or dated.
- **1.5 Service levels and run model.** 90-day warranty after Gate 6; Sev 1 response 2 business hours and
  workaround within 1 business day, Sev 2 response 4 business hours and fix within 3 business days, Sev 3
  response 1 business day; a run model (operating owner, monitoring ownership and alert routing, severity
  definitions and escalation, hand-off to warranty and to the AMS partner, indicative run cost) agreed before
  Gate 4 in A-D20 / B-D20. Stage 6 adds a Knowledge Transition to Ingredion's AMS partner: plan by the end
  of Stage 5, sessions, reverse shadowing (the partner operates the agent with Parkar support), sign-off at
  Gate 6.
- **1.7 Ownership and IP.** All Agent Work Product is Ingredion's and is held only in Ingredion's repository;
  Parkar identifies pre-existing materials in writing before incorporating them and may use them only with
  Ingredion's approval (with a perpetual licence to Ingredion and its AMS partners); third-party and
  open-source components are listed in A-D16a / B-D16a with licences; no training on Ingredion data; no
  copies retained after closure. **The shared `factory/` runtime in this folder is such pre-existing
  material and must be declared before Stage 3; the code must move into Ingredion's repositories in week 0.**
- **Deliverables and measures.** New A/B-D16a technical build documentation, D16b baseline test cases
  Ingredion expands for SIT and UAT, D16c developer test cases with results, all before Ingredion testing
  (2.6, 3.7). Agent A scorecard and reporting (2.7): completion rate, field-level accuracy, undetected
  errors, reviewer confirmation, handling time, run cost; thresholds set at Gate 1 from the 500-PO backtest;
  twelve reporting measures from Stage 5.
- **People.** Appendix 3 (roles per agent, committed capacity, named key persons, FTE by week) is Parkar's
  to provide before signature; key persons are not replaced without Ingredion's approval and overlap two
  weeks; Ingredion names a Project Manager before signature (8.2(c)); third parties Accenture, NTT Data and
  Infosys are managed by Ingredion (8.1(a)). Requirements derived from all this: `Ingredion_Client_Requirements.pdf`.

| File | What it is | Date |
|---|---|---|
| `Ingredion Email Order Intake - SOW Scope Sections Simplified - 6 Oct client inputs.docx` | Order Intake SOW scope sections Draft 3.0: background, current and proposed architecture (10 RPA steps, A1–A8), in/out of scope, client responsibilities, assumptions, stages and gates, environments, D1–D26, team, payment milestones, RACI | 6 Oct 2026 |
| `Ingredion Email Order Intake - SOW Walkthrough.pptx` | Nine-slide walkthrough of the same SOW for the 7 Oct review (failure analysis chart, A1–A8, architecture, measures, 18-week plan, scope, client responsibilities) | 6 Oct 2026 |
| `Email Order Intake Agent Responses to SOW Clarification Questions.docx` | Parkar's answers to Ingredion's twelve clarification questions: failure recovery scope, CMIR validation, thresholds, Salesforce fields, price/contract/availability checks, UOM, baseline, failed-case recovery, duplicates, operational controls, reviewer experience, data governance and Canada | added 19 Oct 2026 |
| `Pre-bill Validation Agent - Technical Solution Walkthrough.pptx` | Parkar SOW Draft 1.1 technical walkthrough: solution, architecture, six stage gates, 16-week plan, scorecard | 10 Oct 2026 |
| `PreBill_Validation_Dispute_Prevention_Briefing.pptx` | Ingredion business briefing (lead Soochul Kim, DTS): problem, evidence, future state, data-trust table, rollout, PoC calendar, RACI, risks | 2 Oct 2026 |
| `AI Initiatives - Ingredion - Project Governance.xlsx` | Governance workbook for the Order Intake agent: actions, stakeholders, meetings (24 Sep, 5 Oct, 7 Oct), comms plan, empty RAID log | Sep–Oct 2026 |
| `09-24-2026-Ingredion _ Parkar AI Initiative Discovery Session ... .docx` | Transcript of the first discovery call (email order intake use case, Parkar references, staffing) | 24 Sep 2026 |
| `Media (4).jpg` | Whiteboard sketch of the pre-bill workflow, reviewed on 16 Oct | 16 Oct 2026 |
| `NA NoTouch Error Analysis - ShipTo.xlsx` | Ingredion's RPA failure analysis for 1 June to 31 July 2026 (the figures quoted in SOW 2.2): 1,180 failed cases with the raw bot error messages, 16 error types, pivots by Customer and Ship-To, and a no-touch baseline (4,000 cases, 1,500 errors). Analysed in section 11; tables regenerated by `tools/rpa_error_analysis.py` into `rpa-failure-analysis-tables.md` | received 23 Oct 2026 |

## 1. The programme: "Ingredion Agentic AI Factory"

Two agents in the order-to-cash flow, both as managed code on Microsoft Azure inside the Ingredion
tenant, both eight steps with generative AI in exactly two of them, one human gate and an
append-only audit trail. The Order Intake deck states the design intent: later agents plug into
the same pipeline, audit trail and evaluation suite.

1. **Email Order Intake Agent** — Part A of SOW No. 07 (redline v2, 20 Oct; earlier Draft 3.0 of
   6 Oct and the clarification responses). Processes all email orders and is designed to replace the
   Existing RPA. **The only agent that writes** (SAP sales order, Salesforce case), after a reviewer.
2. **Pre-bill Validation and Dispute Prevention Agent** — Part B of SOW No. 07 (earlier Draft 1.1, 10 Oct).
   Between shipment and invoice. Writes to no Ingredion system. Named in the Order Intake SOW as a
   separate initiative; the Order Intake agent stores price discrepancies in a form pre-bill can reuse.

People. Sponsor: Matt Levin (VP IT). Ingredion lead: Sridevi Matam (Principal Data Scientist).
AI/ML director: Brian Chau. Pre-bill business lead: Soochul Kim (Sr Consultant, DTS). Parkar: Amit
Gandhi (CTO), Hardik Desai (AVP Cloud AI, architect), Ananya Mehta (engineer), Niti Bhargava (TPM,
onsite), James Ambrose and Sachin Fasale (account), Gaurav Singh (CEO). Ingredion's third-party
providers: Accenture (runs the Existing RPA and the SIEM), NTT Data (Vista), Infosys.

## 2. Email Order Intake Agent (use case 1)

### 2.1 Today's flow and where it fails
Ten steps across Outlook, Salesforce, Power Automate, Azure Document Intelligence (a custom OCR
model per customer), a SQL mapping database (stored procedures validate and enrich) and the SAP API.
Customer Service triages each case; eligible cases go to the Bot Queue; the bot takes one case at a
time, retrieves the PDF, OCRs it, validates and enriches through the stored procedures, builds the
payload and submits to SAP. Failures are logged in the **PurchaseOrder PDF table** (OCR data plus
error) and go to rework: optimization bots first, then manual review.

Failure analysis, North America, 1 Jun–31 Jul 2026: **1,180 failed records, 133 customers**
(1,178 categorised + 2). Extraction 532 (45%): line totals do not add up 133, no line items 130,
zero quantity 96, labels 64, total or price not numeric 55, date format 54. Mapping data 439 (37%):
customer material not in the database 277, multiple customer-material profiles 119, customer
mapping missing 29, no model ID 14. SAP 175 (15%): PO already created 157, sales order number not
generated 18. MAX load exceeded 32 (3%). Two uncounted exits: cases not sent to the bot (changes,
cancellations, inquiries) and no usable PDF (order in the email body). Optimization bots alone
complete about 9% of failed cases (120 of 1,344). Earlier discovery figures: ~5,200 POs/month,
10+ mailboxes; Jan–Jul 2026 29,000 POs, 5,000 via RPA, 21,000 manual.

### 2.2 The agent — eight steps, generative AI in A2 and A3 only
Runs on Azure Functions in the Ingredion tenant. Every write is ordinary code.

| Step | Integration | What happens | Exit |
|---|---|---|---|
| A1 Pick up the RPA-failed case | failure record (read-only, polled, last record tracked); Salesforce case | Identify the failed case and error; read the original email body and attachments; claim the case | none |
| A2 Classify the email and RPA error | Foundry model; Prompt Shields + Content Safety first | New order with an in-scope failure? Change, cancellation, inquiry, credit memo, non-English, handwritten exit | rework path with reason |
| A3 Read the PO with generative AI | Foundry model + Document Intelligence | PDF, scanned image, Excel, email body → fields with confidence; multi-PO email split into separate orders (TBC); prompts and models versioned | none; a field failing validation is re-read once |
| A4 Validate and enrich | SAP master data incl. CMIR (read); UOM from SAP conversion data; mapping DB / stored procedures only if kept (Stage 1 comparison) | Sold-to, ship-to, bill-to, material matched; UOM converted, never assumed (missing / invalid / ambiguous → reviewer) | master data missing or not matched → gap reported, rework path |
| A5 Score confidence and business rules | SAP orders (read); price, contract, availability sources (TBC) | Field confidence, duplicate-order check (ship-to, bill-to, PO no., product, date, quantity), price / contract / availability checks → flags with both values, difference, source, reason code; draft clarification email | every case → reviewer under this SOW |
| Human judgment gate | review queue (location: Stage 2) | PO beside the summary, doubtful fields highlighted, SAP candidates, reason codes; approve, correct or reject | rejected → rework path |
| A6 Build the SAP payload | agent code | Same payload the RPA builds, from validated, enriched, reviewer-corrected data | none |
| A7 Create the sales order | SAP order API via Azure API Management (**write**) | Submit and check creation; on timeout look the order up, retry ×3 with increasing waits, then exit "SAP unavailable" and alert; pause if SAP is down for all | SAP rejects → rework path with the SAP error |
| A8 Update the Salesforce case | Salesforce (**write**) | Order number, status, audit note; marker "Processed by: Agent" with outcome Agent-created / Agent-assisted / Returned | none |

Release 1 treatment by category (clarification responses): extraction failures attempted;
mapping-data failures where SAP holds the data attempted; multiple profiles attempted when SAP gives
one match, else the reviewer chooses; price / contract / availability mismatch flagged with a draft
clarification email; possible duplicate flagged, closed as duplicate if confirmed; data missing in
SAP, SAP rejects, non-orders, handwritten / non-English, MAX load exceeded → rework path with reason.
Note the drift from Draft 3.0, which exits mapping-data and SAP causes at A2 and lists contract
price, allocation limits and products not sold as out of scope; the later position is the one above.

### 2.3 Scope, assumptions, measures
- In: fallback for RPA-failed cases; extraction failures first; end-to-end processing to SAP and
  Salesforce; PDF, scans, Excel, email body; master-data validation incl. CMIR; duplicate check;
  managed code with CI/CD; adaptable models; audit and monitoring; reviewer confirmation (assisted mode).
- Out: pre-bill and other use cases; run and support after hyper care (separate SOW); handwritten
  and non-English POs; any change to the Existing RPA or PO Portal; master-data, mapping and CMIR
  corrections (reported only); cases the RPA completes and non-order emails; work inside SAP or
  Salesforce incl. new SAP interfaces; enterprise AI governance, observability platform, SIEM, SAP AI;
  penetration testing; licences and cloud costs; change management beyond the reviewer guide.
- Assumptions: RPA stays and is run by its owner; failed cases identifiable without changing the RPA;
  500 historical RPA-failed POs with final SAP orders (draft value); English PDF or email POs; Azure
  in the Ingredion tenant with Foundry; Ingredion's Git platform; existing SAP and Salesforce
  interfaces; non-production systems available; no masking of non-production PO data.
- Measures: Stage 1 backtest on 500 POs vs final SAP orders as answer key; field-level accuracy by
  field, customer and failure type; undetected errors (confident but wrong); recovery rate (all key
  fields match: sold-to, ship-to, material, quantity, UOM, price, requested delivery date, PO number).
  Proposed: recovery ≥ 50% at Gate 1, ≥ 70% at Gate 4, ≥ 80% before Phase 2; undetected errors ≤ 2%
  of key fields at Gate 1, ≤ 0.5% before Phase 2. Shadow mode 2 weeks (nothing posted), assisted
  mode 2 weeks (reviewer confirms each result). Phase 2 straight-through = Ingredion decision at Gate 5.
- Controls: one case processed once (case ID + PO number); duplicate check at A5; lookup before any
  retry; Ingredion-controlled kill switch; Azure Monitor dashboards and alerts (failures by reason,
  SAP errors, review queue, agent stopped, cost); per-email audit record, updated never deleted;
  corrections feed the evaluation set, no self-learning; every prompt, model, threshold and rule
  change versioned, re-evaluated and approved by a person; retention per Ingredion policy.

### 2.4 Delivery (SOW No. 07)
Start 26 October 2026 (week 0, both agents). Agent A: 18 weeks including week 0 to Gate 5, plus 4 weeks
hyper care (weeks 18–21), Gate 6 at week 22. Week 0 mobilisation (user IDs and access, one repository per
agent, the Dev GCP project, the 500-PO historical sample within 5 working days of the start). Stage 1
weeks 1–3, Gate 1 at week 3 (sponsor; no payment at this gate; A-D1–A-D7: baseline, exception map, target
architecture, interim review, prototype and backtest report, business case and pilot plan, executive
readout; validation location decided). Stage 2 weeks 4–5, Gate 2 (technical lead; A-D8–A-D12; architecture
and security review). Stage 3 weeks 6–10, Gate 3 (A-D13–A-D16c incl. build documentation, baseline and
developer test cases; evaluation passes in Dev). Stage 4 weeks 11–13, Gate 4 (A-D17–A-D20; UAT signed off,
thresholds met, 5.4 testing complete with no open critical or high findings, run model agreed, production
change approved). Stage 5 weeks 14–17, Gate 5 (sponsor; A-D21–A-D23; shadow 2 weeks then assisted 2 weeks;
Phase 2 decision). Stage 6 weeks 18–21, Gate 6 at week 22 (run owner accepts; AMS partner signs off the
Knowledge Transition; A-D24–A-D26 incl. runbook, reviewer guide, closure report with the evidence for the
decision on the Existing RPA). Team (1.6, 11.4): six offshore people in four roles for Agent A and five for
Agent B in Pune; two shared onsite roles at Westchester, IL (Forward Deployed Engineer up to 40 h/week,
Business Analyst / Program Manager up to 20 h/week; hourly, capped); Program Manager and Solution Architect /
Sr Tech Lead shared and not charged separately; detail in Appendix 3. Ingredion decides and reviews within
5 working days; silence on a deliverable is acceptance; delays move the plan day for day, subject to the
dependency-attribution clause (8.2(c)). Client responsibilities (8.1): named sponsor / technical lead /
use-case lead and a Project Manager, SMEs, management of Accenture / NTT Data / Infosys, Dev–Test–Prod GCP
projects with Vertex AI and approved models, SAP read access incl. CMIR, orders and the incompletion log,
Graph permissions and a service identity, Salesforce permissions, the 500-case sample within 5 working days,
data classification and AI-use approval, Ingredion-side changes by the Gate 2 dates, UAT users and
reviewers, a run owner.

### 2.5 Open items (Order Intake)
Validation source (SAP master data vs mapping database) and whether stored procedures stay; SAP read
interfaces; price / contract / ATP sources; multi-PO representation on one Salesforce case; claim
status and the bot change that skips claimed cases (Gate 2); Salesforce fields and statuses; review
queue location; reason-code catalogue; suggested match on CMIR candidates; MAX load cause; Canada
through the same systems (French POs out); baseline period (week 0); commercial treatment on missed
criteria; post-hyper-care support; retention periods.

## 3. Pre-bill Validation Agent (use case 2) — the problem

The PO is fixed at order entry; SAP sets the final price and freight at shipment; SAP auto-creates
the invoice within 24 hours of delivery; nothing checks the invoice against the PO before it is sent;
the customer portal (e.g. Ariba) three-way match then fails → rejection, short-pay, dispute, credit
and re-bill. Six sources are searched by hand today: TermSync, Salesforce, SAP, PROS, Ariba, and the
contract and fuel-rate files.

Baseline (root-cause analysis, 6 Aug 2026, US & Canada): 26,860 open or late invoices; 3,155 coded
Pricing Discrepancy (11.7%); 674 coded Freight Bill Disputed (2.5%). These are money at risk, not
savings; the preventable share is measured in Stage 1. ~$75M/month may ship without a contract
price — that belongs to the pricing teams and is explicitly out of scope (flag only).

### Anchor test case — Kraft Heinz sales order 809-6862 (all four must be caught)

| Check | Customer PO | Invoice | Cause | Rule (proposed, confirmed at Gate 1) |
|---|---|---|---|---|
| Unit price | USD 40.14 / CWT | USD 47.00 / CWT | PO used July's monthly price for an August shipment | Exact match after approved UOM and currency conversion |
| Fuel surcharge | not on PO | USD 300 flat | In the contract, not on the PO | Any charge not on the PO is flagged |
| Quantity | 170,000 lb | 170,250 lb shipped | Full pallets; Ariba hard-blocks over-quantity | Must fall within the PO range; over-shipments checked first; no stated tolerance = exact |
| Payment terms | 120 days | 110 days | PROS had no Net 120 option | Exact match |

Which source wins: SAP is the record of what will be invoiced; the PO is what the portal matches
against. If SAP is right → the customer updates the PO. If SAP is wrong → Ingredion fixes its side.
If unclear → a person decides.

### Data-trust table (proposed, owners TBC on 23 Oct)

| Item | Customer expects | Official source | Date that applies | Allowed variance | Who resolves |
|---|---|---|---|---|---|
| Unit price | PO price | SAP-calculated price (contract / PROS) | Billing date (actual goods issue) | Exact after UOM (e.g. BAG→KG) and currency conversion | Pricing & Billing |
| Freight | PO freight line / agreed terms | SAP freight calculation (some manual) | Ship date | Any charge not on PO flagged | O2C ownership |
| Fuel surcharge | PO or agreement | SAP surcharge condition (some rail manual) | Ship date | Any charge not on PO flagged | Pricing & Billing |
| Quantity | PO qty and tolerance | Quantity shipped | Ship date | PO range after UOM; none stated = exact | Customer Service / O2C |
| Payment terms | PO terms | SAP customer master / contract | Contract effective date | Exact (backstop) | AR & Collections |

## 4. Pre-bill agent — eight steps, one human gate

Runs between shipment and invoice submission. Generative AI is used in **B3 and B6 only**, through a
Microsoft Foundry model endpoint; everything else is ordinary, testable code. A matched invoice
skips B6 and B7 and is recorded at B8.

| Step | Kind | What it does |
|---|---|---|
| B1 Pick up the invoice | code, SAP read | Identify shipped orders with a draft invoice ready to send |
| B2 Assemble evidence | code, six sources read | Collect PO, shipment, draft invoice, SAP price record, rate files. Missing data (incl. missing SAP price) is flagged, never passed as clean. Later: price-discrepancy records from Order Intake A5 |
| B3 Read the PO | tiered; Gen AI fallback | Structured PO data first (portal, SAP, Salesforce); Gen AI reads PDF POs only when needed; Document Intelligence only for scans. Guardrails screen PO text before any model call |
| B4 Normalise and match | code | Unit and currency conversion; match each PO line to its SAP line |
| B5 Compare | rules, code | Three-way match on the four checks → **Matched** / **Updated PO required** / **Internal fix or missing data** |
| B6 Explain and draft | Gen AI, Foundry | Summary of each gap by category with evidence; draft PO-update request or internal fix note |
| B7 Route | human gate | Review queue → IGS or Customer Service owner mailbox (agreed in Stage 1). Owner confirms or overrides. No case skips this |
| B8 Record | code, audit trail | Decision, reason, evidence per order, never deleted. When an updated PO arrives, recheck from B2; close when aligned |

Outputs are only: the review queue, the drafted PO-update request, and the audit trail. The agent
**writes to no Ingredion system** (SAP, PROS, Salesforce, portals stay as they are). People act on a
case outside the agent.

In scope: find PO/shipment/invoice gaps that would fail the portal match; tell valid changes from own
errors; flag missing SAP prices and data; summary by category for the owner; draft the PO-update
request; recheck when the updated PO arrives. Out: order-entry checks (Order Intake use case); fixing
missing prices; changing SAP or PROS; releasing invoices or contacting customers; tracking acceptance,
payment and disputes after sending. Rollout of checks: price and freight/surcharge first; then
quantity; then payment terms (backstop; root fix is at contract/order setup).

## 5. Shared target architecture (the factory)

- Managed code on Azure in the Ingredion tenant; Order Intake on Azure Functions; both follow the
  same platform pattern. One repository per agent in Ingredion's enterprise Git platform (GitHub,
  Bitbucket or Azure DevOps) holds code, prompts, rules, configuration and infrastructure-as-code;
  PR-based; the pipeline releases Dev → Test → Prod; everything stays with Ingredion at handover.
- Shared components, built once: case intake adapters, guardrails (Prompt Shields, Content Safety)
  and the Foundry model gateway with Document Intelligence and versioned prompts, rules and scoring
  with one reason-code catalogue, review queue, append-only audit trail, evaluation suite (backtest,
  holdout, regression on every build), observability (Foundry tracing → Application Insights,
  OpenTelemetry; Azure Monitor dashboards and alerts; kill switch), managed identities and Key Vault.
- Identity: one read-only identity for all reads; a separate write identity held only by Order Intake
  A7 and A8 (SAP order API via APIM, Salesforce case update). Pre-bill never receives a write role.
- Second human gate: a person approves every prompt, model, threshold, rule and variance change
  after evaluation. No self-learning.
- Out of both SOWs: NTT Vista connection; SIEM export (Accenture); SAP AI. Logs kept exportable.
- Environments: Dev (Stage 1 prototype and backtest, Stage 3 build; historical data), Test (Stage 4;
  configured like Prod; unseen historical data), Prod (Stage 5 shadow and assisted, Stage 6 hyper
  care; live cases only).

## 6. Stages, gates and dates (SOW No. 07; start 26 October 2026)

| Stage | Agent A · Order Intake | Agent B · Pre-bill | Gate decided by |
|---|---|---|---|
| 0 Mobilisation | week 0 (w/c 26 Oct 2026) | week 0 | — |
| 1 Discovery & Assessment | weeks 1–3, Gate 1 wk 3 (w/c 16 Nov) | weeks 1–3, Gate 1 wk 3 | Sponsor (go/no-go; validation location) |
| 2 Solution Design | weeks 4–5, Gate 2 wk 5 (w/c 30 Nov) | weeks 4–5, Gate 2 wk 5 | Technical lead (design approval) |
| 3 Build | weeks 6–10, Gate 3 wk 10 (w/c 4 Jan 2027) | weeks 6–9, Gate 3 wk 9 (w/c 28 Dec) | Sponsor (evaluation passes in Dev; D16a–c delivered) |
| 4 Test & Validation | weeks 11–13, Gate 4 wk 13 (w/c 25 Jan) | weeks 10–12, Gate 4 wk 12 (w/c 18 Jan) | Sponsor (UAT, thresholds, 5.4 findings closed, run model) |
| 5 Production Release | weeks 14–17 (shadow 2 + assisted 2), Gate 5 wk 17 (w/c 22 Feb) | weeks 13–15 (shadow 1 + assisted 2), Gate 5 wk 15 (w/c 8 Feb) | Sponsor (Phase 2 for A; later dispute types for B) |
| 6 Hyper Care & Handover | weeks 18–21, Gate 6 wk 22 (w/c 29 Mar) | weeks 16–19, Gate 6 wk 20 (w/c 15 Mar) | Run owner, with the AMS partner's Knowledge Transition sign-off |

Stage 1's three weeks count from the day access and the historical sample are both in place (8.2(c)), so
the dates hold only if the week-0 items land. Gate decisions are per agent and are given within 5 working
days of the gate review (4.2). The pre-bill 10-week PoC calendar in Ingredion's brief of 7 October (decision
point 23 Oct, Gate 1 target 18 Dec 2026) is superseded by this plan (SOW 7.0).

## 7. Pre-bill scorecard (Gate 4 and Gate 5; thresholds confirmed at Gate 1)

| Measure | Scale up | Extend if | Stop if |
|---|---|---|---|
| Catch rate (incl. Kraft Heinz 4/4) | ≥ 95% | 85–95% | < 85% |
| False alarms on clean invoices | ≤ 10% | 10–20% | > 20% |
| Traceability (flag → source record + rule) | 100% | ≥ 95% | < 95% |
| Reviewer agreement | ≥ 85% | 70–85% | < 70% |
| Time saved per case vs Stage 1 baseline | ≥ 30% | 15–30% | < 15% |
| Actions taken without a person | 0 | — | any |
| Missing data flagged | 100%, in ≤ 15% of cases | 15–25% | any missed flag or > 25% |

Test set must include clean, single-error, multiple-error, missing-data and borderline cases, not
only the anchor order.

## 8. Pre-bill ownership (proposed RACI; owners confirmed in Stage 1 per SOW No. 07 section 3.6)

| Issue type | Fixes | Approves | Consulted | Releases invoice |
|---|---|---|---|---|
| Price change | Pricing & Billing | O2C ownership | Sales, Customer Service | O2C ownership |
| Freight / surcharge | Pricing & Billing | O2C ownership | Customer Service, logistics | O2C ownership |
| Quantity | Customer Service | O2C ownership | Plant / logistics | O2C ownership |
| Payment terms | AR & Collections | Financial systems & governance | Pricing & Billing | O2C ownership |
| Missing information | PoC lead, IT data owners | Financial systems & governance | Data owners | none — a person handles it |
| Requesting the updated PO | Customer Service / Pricing & Billing | O2C ownership | Sales, AR & Collections | after updated PO matches |
Escalation for all: Sponsor.

Pre-bill open items: Parkar technical session; where the check runs; which source wins; named owners
per issue type; the updated-PO request process (who, channel, SLA, fallback when late); acceptable
variances; data access (Ariba/TermSync read); B7 notification channel; Azure services list; Finance
reviewer for value.

## 9. Engineering review (19 Oct) — summary

Twelve points to settle in Stages 1–2, detailed in the workflow page: (1) scope drift between Draft
3.0 and the clarification responses; (2) route on the RPA error code in code, model reads intent only;
(3) computed, calibrated confidence instead of self-reported; (4) re-run A4/A5 after reviewer
corrections; (5) exactly-once around the SAP write (write-ahead state, reconciliation on restart, A8
retried independently); (6) bot-concurrency change as a Gate 4 entry criterion; (7) multi-PO emails
vs one case per email; (8) email-body-only POs may not reach the failure record; (9) backtest answer
key contains information not in the PO; (10) one review app for both agents; (11) read/write identity
split; (12) language detection at A2 (Canada in, French out).

## 10. What Parkar brought as reference (from the 24 Sep call)
Hospitality revenue-cycle invoice agent on Azure Foundry with Anthropic vision OCR: ~93% straight-
through, ~USD 250–300/month tokens at 3–5k invoices, daily/weekly human reconciliation, per-step
audit trail, soft-delete-and-insert for change history, L1/L2/L3 agent operations on Azure Monitor.
Delivery shape: 3–4 week assessment, ~2.5 months to first production version, then a month of
eval/feedback maturing.

## 11. The RPA failure analysis workbook (received 23 October 2026)

`NA NoTouch Error Analysis - ShipTo.xlsx` is the analysis SOW No. 07 quotes in section 2.2: 1,180 failed
cases of the Existing RPA between 1 June and 31 July 2026 (case numbers 2026-0529 to 2026-0731), 133
Customer names (116 once spelling variants are merged), 159 ship-tos, 16 error types, two uncategorised.
Sheets: `Raw Data` (EmailDate, Customer, CaseNumber, Status, ErrorMessage, ShipTo), `Overall Error Types`
(the 16 categories with Ingredion's failure point and description), pivots by Customer and Ship-To,
`Current Breakdown` (the no-touch baseline) and `Ship-To Summary`. Everything below is reproducible with
`python tools/rpa_error_analysis.py "NA NoTouch Error Analysis - ShipTo.xlsx" --markdown rpa-failure-analysis-tables.md`
(needs `openpyxl`; the classifier it uses is `order_intake_agent/rpa_errors.py`).

**The no-touch baseline (sheet `Current Breakdown`, period as stated by Ingredion).** 4,000 cases, 1,500
errors: a 62.5% no-touch rate. Of the errors, 1,344 went to the optimization bot; 120 (8%) succeeded on
retry, 615 (41%) succeeded after a person ("John") fixed the data, 609 (41%) were done manually anyway
(about 340 failed even after all data was added, about 270 for assorted manual reasons). So 65.5% of cases
reached SAP without a person touching data. This is the figure the Agent A completion rate is judged
against (SOW 2.7); the 1,180 classified records are a subset of the 1,500 errors (the 320 gap is a question
for Ingredion, as is the exact period of the 4,000).

**Error types and where the agent absorbs them** (Ingredion's counts; failure point in Ingredion's words):

| Error type | Cases | Ingredion's failure point | Agent step | Addressed | Reason code the agent raises instead |
|---|---|---|---|---|---|
| Customer Material Not Available | 277 (23.5%) | Database | A4 | partly: resolved if the material exists in SAP CMIR, else reported | MASTER.MATERIAL_NOT_FOUND |
| PO Already Created (the bot's own duplicate check) | 157 (13.3%) | SAP | A2 / A5 | routing: duplicate or revised PO, closed or sent to the reviewer | EMAIL.DUPLICATE_SUBMISSION |
| Sum of Line Total Validation | 133 (11.3%) | OCR | A3 / A5 | by design | EXTRACT.LINE_TOTALS_MISMATCH |
| No Line Level Items | 130 (11.0%) | OCR | A2 / A3 | by design (includes T&C attachments the bot ran as POs) | EXTRACT.NO_LINES |
| Multiple Customer Material Profiles | 119 (10.1%) | Database | A4 | partly: ship-to disambiguated from the PO address, else reviewer | CMIR.MULTIPLE_MATCHES |
| Zero Quantity (quantity ÷ SAP bag weight ÷ pallet = 0) | 96 (8.1%) | OCR | A3 / A4 | by design | EXTRACT.ZERO_QUANTITY |
| Delivery Date Format | 54 (4.6%) | OCR | A3 | by design | EXTRACT.DATE_FORMAT |
| Missing Label Names | 50 (4.2%) | OCR | A3 | by design (no per-customer labels) | EXTRACT.LOW_CONFIDENCE |
| Grand Total Not Numeric (all 44 at one Customer) | 44 (3.7%) | OCR | A3 | by design | EXTRACT.NOT_NUMERIC |
| Customer Material Exists MAX Load | 32 (2.7%) | Database/OCR | A3 / A5 | partly: misreads removed, real breaches flagged | QTY.MAX_LOAD (new code) |
| Customer Mapping Missing | 29 (2.5%) | Database | A3 | by design (see note) | EXTRACT.NO_LINES |
| Sales Order Number Not Generated | 18 (1.5%) | SAP | A9 | by design (lookup before retry, incompletion log) | SAP.RECONCILED |
| Label Values Not Extracted | 14 (1.2%) | OCR | A3 | by design | EXTRACT.LOW_CONFIDENCE |
| No Model ID (no OCR model for the account) | 14 (1.2%) | Database | A3 / A4 | by design | MASTER.SOLD_TO_NOT_FOUND |
| Unit Price Not Numeric (the price column held "LB") | 11 (0.9%) | OCR | A3 | by design | EXTRACT.NOT_NUMERIC |
| Miscellaneous | 2 | — | A1 | reported | EXTRACT.FORMAT_ERROR |

Ingredion's split is OCR 532 (45%), database 439 (37%), SAP 175 (15%), MAX load 32 (3%), exactly the SOW
2.2 figures. Read from the messages, the 29 "Customer Mapping Missing" cases are line-item label failures of
the customer's OCR model (Ingredion assigned the category from its mapping database, not from the text), so
extraction is nearer 561 (47.5%) and mapping data 410 (34.7%). By how the agent handles them: 593 (50%)
cannot recur by design, 428 (36%) are resolved when the data exists in SAP and otherwise reported, 157 (13%)
are duplicates to route, 2 are unknown. `rpa_errors.classify_rpa_message` reproduces Ingredion's counts
exactly for 11 of the 16 categories; the rest differ by a handful of concatenated messages, and "Customer
Mapping Missing" cannot be derived from the text.

**Concentration, which is what the cohort decision needs.** The top 10 ship-tos hold 575 failures (49%),
the top 10 Customer names 621 (53%); 94 of the 159 ship-tos show a single error type. Single-cause ship-tos
where a generative reader removes the whole failure class: Sweets Mix Company 101671 (44 of 44 grand total
not numeric), Batory Foods 2065 (74 of 127 zero quantity), Ken's Foods 121465 (55 line-total and 24 MAX
load of 83), IFF 2263 (17 of 19 date format), Kerry Ingredients 123064 (28 of 42 no line items). Sweetener
Supply 101372 (41 of 61 "PO already created", revision suffixes -R493 to -R496) is a duplicate-handling case,
not an extraction one. Skidmore 121058, ICI Foods 124270 and International Food Products 125594 are
master-data cases (material not available, multiple profiles) whose outcome depends on SAP CMIR.

**Volume by week** (case-number date): W22 16, W23 89, W24 97, W25 79, W26 107, W27 128, W28 181, W29 158,
W30 94, W31 231, so failures rose through July. The `EmailDate` column is the bot's run timestamp (39 records
share one stamp), so the case number is the usable date.

**Data quality to carry into the sample and the backtest.** Failures only, no successes, so this file alone
cannot give the automation rate per cohort or the 500-PO sample, which SOW 8.2(b) wants "including RPA-failed
POs" in the real mix (errors are 37.5% of cases). Customer is free text (NEWLY WEDS FOODS appears in six
spellings; AGRANA in four), so cohorts must key on SAP sold-to and ship-to numbers; 46 records have ship-to
N/A. Messages are HTML-escaped with `<br>` separators; 84 show the bot running a second attachment (terms and
conditions PDFs) after a success, 126 carry more than one failure; 15 records have no attachment name (email
body orders). `Customer x Error Type` has 134 rows for 133 names.

**What this changes in the asks.** Requirement item 6 is partly met: the failure analysis is in hand; still
needed are the full ~4,000-case population with outcomes by customer and ship-to (for the baseline rate and
the sample), a CMIR extract for the 396 material and profile failures (Stage 1 measures how many exist in
SAP, SOW 8.2(a)), and Ingredion's answer on the 1,500 versus 1,180 gap and on the ~340 cases that failed
even after their data was fixed, which bound what any agent can complete. For Gate 1 the scorecard needs a
rule for how a correctly closed duplicate counts in the completion rate, because 13% of failures are
duplicates.
