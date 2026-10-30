// Agent A: Email Order Intake Agent. Agent-specific content plus the parameters for the shared sections.
const { H1, H2, H3, P, UL, OL, T, CODE, NOTE, mon, fri, friD, by, span } = require("./lib");

const g1 = friD(3), g2 = friD(5), g3 = friD(10), g4 = friD(13), g5 = friD(17), g6 = friD(22);

const agent = {
  letter: "A", name: "Agent A, the Email Order Intake Agent", short: "Agent A", pkg: "order_intake_agent",
  steps: "A1 to A10", delivSection: "2.6", processSection: "2.3", scorecardSection: "2.7",
  writes: "A6 (an Outlook draft the reviewer sends), A9 (the SAP sales order) and A10 (the Salesforce case)",
  saName: "order-intake-agent", service: "ingredion-order-intake",
  pollCall: "runtime.poller.poll_once()",
  envExtra: "ORDER_INTAKE_MODE=primary,GRAPH_DRAFT_MAILBOX=orders@ingredion.com",
  networkIntro: "Agent A reaches three systems outside Google Cloud: SAP through Azure API Management, Salesforce, and Microsoft Graph for the shared mailbox.",
  modelSteps: "A2 (intake classification), A3 (extraction) and A6 (drafting the Customer clarification)",
  promptDir: "order_intake", promptFiles: "`a2_classify.v2.md`, `a3_extract.v1.md`, `a6_exceptions.v1.md`",
  outputGuard: "the A6 clarification draft and the A7 review summary", docAIStep: "A3",
  g3, g4, g5, g6, stage3End: 10, evalCmd: "order-intake", evalNote: "prints how the backtest is scored; the scorer runs in the tests until the sample arrives",
  authzTest: "prove it can create a draft but not send mail, can create an SAP order only through the approved method, and can update only the agreed Salesforce fields (a write to any other object must be refused by Salesforce, not just avoided by the code).",
  dashboardMetrics: "cases received and completed, completion rate per cohort, orders created, incompletion items and follow-ups, cases returned by reason code, reviewer corrections, guard blocks, model latency, tokens and pages per case, queue age and run cost (the SOW 2.7 reporting list).",
  shadowSpan: span(14, 15), assistedSpan: span(16, 17), hyperSpan: span(18, 21), ktSpan: span(19, 20), reverseSpan: span(20, 21), closureSpan: span(21, 22),
  shadowText: "Deploy to Prod under Ingredion change management (A-D21, by " + friD(14) + "). In shadow mode the agent processes live email order cases but creates no SAP order, updates no Salesforce case and saves no Outlook draft; the Existing RPA keeps creating the orders. Make that a policy, not a code branch: add `shadow: bool` to `OrderIntakePolicy` so that A6, A9 and A10 record what they would have done in the audit trail instead of doing it. Compare every result with the order the RPA or a person created for the same case, by cohort, and tune prompts and thresholds through release approval. The comparison is A-D22 and is also the first measurement of completion rate against the RPA's automation rate on the same cohort.",
  assistedText: "Ingredion routes the agreed first cohort to the agent's Salesforce queue by the routing agreed at Gate 2 (by Customer or mailbox cohort, SOW 2.3); from then on the agent is the primary processor for those Customers and the RPA no longer sees them. Every case stops at the reviewer; approved cases are created in SAP by A9 and written back by A10; corrections are captured for tuning; clarification drafts are sent by the reviewer, never by the agent. The kill switch fails back by the same routing change that moved the cohort. Reviewer onboarding (A-D23, week of " + mon(15) + ") comes first; medium security findings close or get dates in this window.",
  gate5Decision: "At the same gate Ingredion decides whether high-confidence cases from known Customers may be created without reviewer confirmation (Phase 2); configuring that afterwards is change control (2.4).",
  closureEvidence: "the evidence for Ingredion's decision on retiring the Existing RPA",
  week0ParkarExtra: "Raise the requests the WBS puts in Week 0: Microsoft Graph permissions for the shared mailbox, the agent's service identity, and the Salesforce access scope (read cases and attachments, update the agent fields).",
  baseline: [
    ["Steps A1 to A10", "Step modules with the SOW's exits, flags and dispositions; pipeline with write-ahead submit, retries, reconciliation and resume after review; harness and tests", "Real inputs and outputs through the connectors; prompts tuned on the backtest; the Phase 1 reviewer flow end to end"],
    ["Model gateway", "`VertexStructuredExtractor` (controlled generation with JSON fallback), `PromptRegistry`, `GuardedExtractor`, `ModelArmorGuard`, prompts a2 v1 and v2, a3 v1, a6 v1", "First real Gemini calls; multimodal input; prompt versions tuned on 500 POs; the Model Armor template wired; response screening"],
    ["Layout readers", "Plain text, Excel, Word, Document AI reader, composite router", "Processor created; routing rule from the sample; page and confidence logging"],
    ["Connectors", "Protocols and Dev stubs for Salesforce, SAP master data, SAP orders, SAP order API, Microsoft Graph, alerts; RPA failure record stub", "Salesforce, SAP via API Management, Graph and RPA-record clients (section 9)"],
    ["Human gate", "Review queue (memory and Mongo), REST router, decisions resume the pipeline, corrections re-run A4 and A5", "Reviewer screen, single sign-on identity, reviewer guide"],
    ["Operations", "Kill switch (env, Mongo, composite), ops router, OpenTelemetry to Cloud Trace, append-only audit trail, closed reason-code catalogue (68 codes)", "Dashboards and alerts, retention jobs, runbook, Cloud Run deployment, pipelines, the 5.4 tests"],
    ["Evaluation", "`score_order_intake` with key fields and gate thresholds; the RPA error taxonomy classifier that reproduces Ingredion's analysis", "The backtest on Ingredion's 500 POs; SIT and UAT evidence; scorecard reporting from the audit trail"],
  ],
  week0Deps: [
    ["Named leads, Project Manager, SMEs (items 1, 2)", "Sponsor, technical lead", "Before " + mon(0), "Book the weekly status, the interim review (week of " + mon(2) + ") and the executive readout (week of " + mon(3) + "); put the Stage 1 walkthroughs in the SMEs' calendars."],
    ["Historical sample: 500 POs incl. RPA-failed, with attachments, RPA/OCR output, failure reasons and final SAP orders (item 5); reference results confirmed", "Use-case lead", "Within 5 working days of " + mon(0) + " (by " + fri(1).replace(fri(1), "2 Nov 2026") + "); confirmation by " + fri(2), "Land it in the samples bucket; run the labelling script (`rpa_errors`) and split by Customer and failure type; record the Stage 1 start date in the RAID log."],
    ["Dev GCP project with Vertex AI, Document AI, Model Armor, Cloud Run and quota (item 16)", "GCP platform team", "Week 0", "Run sections 5.1 to 5.4; make one Gemini call from the prototype on a synthetic PO; create the Document AI processor."],
    ["Dedicated service account, IAM, region (item 17)", "Platform and security", "Week 0", "Bind the roles in 5.2; set Application Default Credentials; run the authorization test skeleton."],
    ["Connectivity approach to API Management, Salesforce and Graph (item 18)", "Network and security", "Decision week 0; path by " + fri(2), "Request the connector and NAT address (or the VPN); send the address for allow-listing; connectors stay on stubs until then."],
    ["Repository with pipeline permissions (item 19)", "Technical lead", "Week 0", "Push the code (3.2); enable branch protection; wire the pipeline (section 12)."],
    ["Data classification and AI-use approval, approved model list (item 20)", "Security and technical lead", "Week 0", "Set `VERTEX_MODEL` to an approved model; file the approval under `docs/`; no real PO reaches Gemini before this."],
    ["Model Armor template (item 21)", "Security", "Stage 1", "Set `MODEL_ARMOR_TEMPLATE`; measure the block rate on the sample."],
    ["Prototype security review within 5 working days of the request (item 22)", "Security", "Request on " + mon(0) + "; clear by " + fri(1), "Raise the request with the architecture sketch on day one; the prototype cannot touch real POs before it clears."],
    ["SAP read interfaces or the GCP data sources holding SAP data (item 9); SAP field requirements and mapping (item 8)", "SAP team", "Week 1; confirmed by " + fri(2), "Feed the validation-location recommendation; write the connector against the confirmed interface; replace the stubs one method at a time."],
    ["Salesforce API access, permissions, sandbox (item 12); routing and agent fields (item 13)", "Salesforce team", "Week 1; routing by Gate 2 (" + fri(5) + ")", "Create the connected-app client; point A1 and A10 at the sandbox; agree the field names."],
    ["Graph permissions and service identity (item 14)", "Microsoft 365 team", "Stage 2", "Register the app; create one test draft in the test mailbox."],
    ["RPA failure record, Power Automate flows, OCR configuration; Accenture engaged (items 3, 15)", "Technical lead via Accenture", "Week 0", "Use it for the baseline (A-D1) and the shadow comparison later; it is not the agent's feed."],
    ["User IDs, VPN, Westchester access, Teams channel (item 25)", "IT and facilities", "Week 0", "Switch `gcloud` and Git to the Ingredion identity; set the onsite calendar for the FDE and BA."],
  ],
  iamRoles: [
    ["roles/aiplatform.user", "Call the approved Gemini model on Vertex AI (A2, A3, A6)"],
    ["roles/documentai.apiUser", "Process scans and PDFs with the Document AI processor (A3)"],
    ["roles/modelarmor.user", "Screen text with the Model Armor template before every model call"],
    ["roles/secretmanager.secretAccessor", "Read the secrets mounted into the service (5.3)"],
    ["roles/logging.logWriter, roles/cloudtrace.agent, roles/monitoring.metricWriter", "Structured logs, traces and custom metrics"],
    ["roles/storage.objectUser on the agent's buckets only", "Source documents and the sample; no project-wide storage role"],
    ["Nothing else", "No Editor, no Owner, no Cloud Run admin on the runtime account; the deployer account deploys"],
  ],
  secrets: [
    ["ingredion-api-key", "Shared secret for the review and ops API until single sign-on replaces it", "app/auth.py"],
    ["mongo-uri", "Connection string of the shared stores (if MongoDB Atlas is chosen in A-D11)", "factory/settings.py"],
    ["salesforce-client-id, salesforce-jwt-key", "Connected app consumer key and the private key for the JWT bearer flow", "connectors/salesforce.py (section 9.1)"],
    ["apim-subscription-key, sap-client-id, sap-client-secret", "Azure API Management subscription and the OAuth client for the SAP APIs", "connectors/sap.py (section 9.2)"],
    ["graph-client-id, graph-client-secret (or certificate)", "Entra app registration for Mail.ReadWrite on the shared mailbox", "connectors/graph.py (section 9.3)"],
  ],
  buckets: [
    ["ingredion-oi-samples-ENV", "The 500-PO historical sample, RPA/OCR output and the final SAP orders (the backtest answer key)", "Read-only after load; kept for the engagement; Dev and Test only (approved historical data, SOW 5.2)"],
    ["ingredion-oi-documents-ENV", "Source emails and attachments per case, keyed by case id", "Lifecycle rule per the 5.3 policy for source documents; event-based hold for legal hold"],
    ["ingredion-oi-audit-export-ENV", "Daily export of the audit trail (optional, for Ingredion's SIEM later, SOW 10.3)", "Retention lock; no delete permission for the runtime account"],
  ],
  reasonCodes: [
    ["NOT_ORDER.CHANGE / CANCELLATION / INQUIRY / CREDIT_MEMO / OTHER", "EXIT", "A2 classifies the email as not a new order; it goes to the manual queue with the reason"],
    ["FORMAT.NON_ENGLISH, FORMAT.HANDWRITTEN", "EXIT", "Out of scope formats (SOW 8.2(b))"],
    ["FORMAT.UNREADABLE", "REVIEW", "No reader could produce text or layout"],
    ["EMAIL.MULTI_PO, EMAIL.REVISED_PO, EMAIL.DUPLICATE_SUBMISSION", "REVIEW", "Several POs in one email; a revision; a PO number already processed"],
    ["GUARD.BLOCKED", "REVIEW", "Model Armor or the pattern guard refused the text; no model call was made"],
    ["EXTRACT.REREAD", "INFO", "A3 re-read the document once after a format error"],
    ["EXTRACT.FORMAT_ERROR, EXTRACT.LOW_CONFIDENCE, EXTRACT.NO_LINES, EXTRACT.ZERO_QUANTITY, EXTRACT.LINE_TOTALS_MISMATCH, EXTRACT.NOT_NUMERIC, EXTRACT.DATE_FORMAT, EXTRACT.PO_NUMBER_MISSING", "REVIEW", "Extraction problems; the field is flagged for the reviewer rather than failing the case"],
    ["MASTER.SOLD_TO_NOT_FOUND, MASTER.SHIP_TO_NOT_FOUND, MASTER.BILL_TO_NOT_FOUND, MASTER.MATERIAL_NOT_FOUND", "EXIT", "Master data missing in SAP; reported to Ingredion, not fixed (SOW 10.2)"],
    ["MASTER.PARTNER_AMBIGUOUS, CMIR.MULTIPLE_MATCHES", "REVIEW", "Several partners or CMIR records match; the reviewer picks"],
    ["UOM.NO_CONVERSION, UOM.INVALID, UOM.AMBIGUOUS", "REVIEW", "Unit cannot be converted to the SAP sales unit, or is ambiguous (TON)"],
    ["DUP.POSSIBLE / DUP.CONFIRMED", "REVIEW / INFO", "Possible duplicate order found in SAP; confirmed duplicate closed by the reviewer"],
    ["PRICE.PO_VS_SAP, CONTRACT.NONE, CONTRACT.OUTSIDE_TERMS, ATP.SHORT, ALLOC.EXCEEDED, PRODUCT.RESTRICTED, QTY.MAX_LOAD", "FLAG", "A5 checks; shown to the reviewer"],
    ["EXCEPTION.UNRESOLVED", "EXIT", "A6 could not resolve the exception; manual queue with the draft attached"],
    ["REVIEW.REJECTED / REVIEW.CORRECTED / REVIEW.RECHECK_FLAGGED", "EXIT / INFO / REVIEW", "Reviewer decisions and the re-run after corrections"],
    ["SAP.REJECTED, SAP.UNAVAILABLE", "EXIT", "A9 could not create the order after the retry policy"],
    ["SAP.RECONCILED", "INFO", "An order found by the lookup before a retry was adopted instead of re-sent"],
    ["SAP.INCOMPLETE", "FLAG", "The incompletion log lists items; follow-ups written to the case by A10"],
    ["KILL_SWITCH", "INFO", "Intake stopped by the operator"],
  ],
};

// ── section 2 ────────────────────────────────────────────────────────────────
function whatYouBuild() {
  return [
    H1("2. What you are building"),
    P("Agent A processes every Customer purchase order that arrives by email and becomes a Salesforce case, and is designed to replace the Existing RPA (SOW 2.1). It reads the PO, maps the fields directly to SAP, validates them against SAP master data without the mapping database, checks price, contract, availability and duplicates, creates the sales order by the method approved at Gate 2, and updates the original Salesforce case. In production under this SOW an Ingredion reviewer confirms every result before the order is created (Phase 1). Cases the agent cannot complete go to the existing manual queue with the reason on the case."),
    H2("2.1 The ten steps and where each one lives"),
    T(["Step (SOW 2.3)", "What happens", "Runs on", "Reads and writes", "Exit", "Module"], [
      ["A1 Pick up the case", "Picks the email order case from the Salesforce queue, claims it, reads the original email and attachments", "Code", "Salesforce (read); claim marker", "None", "`steps/a1_pickup.py`, `factory/intake/`"],
      ["A2 Classify", "New order, revised PO, duplicate or not an order; splits multi-PO emails; guardrails screen the text first", "Gemini", "None", "Not an order: reason recorded, manual queue", "`steps/a2_classify.py`, prompt `a2_classify.v2`"],
      ["A3 Read the PO", "Customer, PO number, materials, quantities, units, dates, prices from PDF, scans, Excel, Word or the email body, with a confidence per field", "Gemini and Document AI", "None", "None; one re-read on a field error", "`steps/a3_extract.py`, prompt `a3_extract.v1`"],
      ["A4 Map to SAP and validate", "Direct SAP fields; customer, ship-to, bill-to, material and CMIR against SAP master data; quantities to the SAP sales unit", "Code", "SAP master data (read)", "Master data not in SAP: reported, manual queue", "`steps/a4_validate.py`"],
      ["A5 Rules and confidence", "Price against SAP and contract, availability (ATP, allocation, restricted products, volume), duplicate-order check, composite confidence", "Code", "SAP pricing, contract, availability, orders (read)", "Gaps or low confidence: flagged to A6 and the reviewer", "`steps/a5_score.py`, `factory/rules/`"],
      ["A6 Exceptions", "Drafts the Customer clarification for missing data, price mismatch, invalid material or revised PO; saved as an Outlook draft", "Gemini", "Microsoft Graph (draft only)", "Unresolved: manual queue with reason and draft", "`steps/a6_exceptions.py`, prompt `a6_exceptions.v1`"],
      ["A7 Review summary", "Summarises the order and flags doubtful fields; the human judgment gate", "Code", "Review queue", "Reviewer rejects: manual queue", "`steps/a7_review_summary.py`, `factory/review/`"],
      ["A8 Build the SAP payload", "The same payload the RPA builds, from validated, enriched and corrected data", "Code", "None", "None", "`steps/a8_build_payload.py`"],
      ["A9 Create the order", "Submits by the approved method, checks creation, reads the SAP incompletion log", "Code", "SAP order API or BAPI via APIM (write); incompletion log (read)", "SAP rejects: manual queue", "`steps/a9_create_order.py`"],
      ["A10 Update the case", "Order number, status, incompletion results, follow-ups and an audit note on the original case", "Code", "Salesforce (write)", "None", "`steps/a10_update_case.py`"],
    ], [2, 4, 1.3, 2.6, 2.4, 2.6]),
    H2("2.2 First release scope (SOW 2.4) and what stays out (SOW 10)"),
    UL([
      "**In:** all email order cases; PDF attachments, scanned images, Excel, Word and email-body POs; an email with several POs becomes separate orders; master-data validation including CMIR and unit conversion; intake classification; price, contract and availability checks; duplicate-order check; manual queue exits recorded on the original case; post-creation incompletion check; reviewer confirmation of every result.",
      "**Out:** changes to the Existing RPA or the PO Portal; correcting master data, CMIR or SAP-side validation failures (reported only); mailbox intake ahead of the Salesforce case; modifications to orders already created; credit memos; sending any email to a Customer without reviewer approval; business rules beyond the listed checks (for example credit status); SIEM and NTT Vista connections; SAP AI.",
      "**Transition (SOW 2.3):** in shadow mode the agent runs alongside the RPA without creating orders; from assisted mode, cases are routed to the agent instead of the RPA bot queue by Customer or mailbox cohort as agreed at Gate 2, so that no case is processed by both; the RPA stays available until Ingredion retires it.",
    ]),
    H2("2.3 The scorecard you are building towards (SOW 2.7)"),
    T(["Measure", "Definition", "Threshold"], [
      ["Completion rate", "Share of email order cases received by the agent that are completed as SAP sales orders", "Set at Gate 1 from the backtest; judged against the RPA's automation rate on the same cohort"],
      ["Field-level accuracy", "Share of extracted fields that match the reviewer-confirmed result and the final SAP order", "Set at Gate 1"],
      ["Undetected errors", "Errors in created orders that the agent did not flag and the reviewer did not catch", "Set at Gate 1"],
      ["Reviewer confirmation", "Share of results confirmed by the reviewer without correction", "Set at Gate 1"],
      ["Handling time", "Average agent processing time and reviewer handling time per case against the Stage 1 baseline", "Set at Gate 1"],
      ["Run cost", "Agent run cost and model consumption per case", "Reported against the Stage 1 estimate"],
    ], [2, 5, 3]),
    P("Parkar's starting proposal from the clarification responses (recovery at or above 50% at Gate 1, 70% at Gate 4, 80% before Phase 2; undetected errors at or below 2% of key fields and 0.5% before Phase 2) is the opening position for the Gate 1 discussion; the backtest numbers decide. The baseline the completion rate is judged against comes from Ingredion's error analysis: 4,000 cases and 1,500 errors in June and July 2026, a 62.5% no-touch rate (see the README, section 11)."),
  ];
}

// ── section 4 ────────────────────────────────────────────────────────────────
function timeline() {
  const stages = [
    ["Week 0 Mobilisation", "0", mon(0) + " to " + fri(0), "none", "Access and the sample in place"],
    ["Stage 1 Discovery and Assessment", "1 to 3", mon(1) + " to " + fri(3), "Gate 1, " + g1, "Sponsor: go/no-go for build; validation location decided; thresholds and plan confirmed"],
    ["Stage 2 Solution Design", "4 to 5", mon(4) + " to " + fri(5), "Gate 2, " + g2, "Technical lead: design approval; architecture and security review complete"],
    ["Stage 3 Build", "6 to 10", mon(6) + " to " + fri(10), "Gate 3, " + g3, "Ready for test: requirements built, evaluation passing in Dev, documentation and test cases delivered"],
    ["Stage 4 Test and Validation", "11 to 13", mon(11) + " to " + fri(13), "Gate 4, " + g4, "Release approval: UAT signed off, thresholds met, no open critical or high findings, run model agreed, production change approved"],
    ["Stage 5 Production Release", "14 to 17", mon(14) + " to " + fri(17), "Gate 5, " + g5, "Sponsor: production acceptance; Phase 2 decision"],
    ["Stage 6 Hyper Care and Handover", "18 to 21", mon(18) + " to " + fri(21), "Gate 6, " + g6 + " (week 22)", "Run owner accepts; Ingredion and the AMS partner sign off the Knowledge Transition"],
  ];
  const comps = [
    { band: "Week 0 and Stage 1" },
    ["Local environment, repository move, pre-existing materials note", "none", "0", by(0), "Repository (item 19)"],
    ["Dev project configured, one Gemini call, Document AI processor", "A-D3 prep", "0 to 1", by(1), "Items 16, 17, 20"],
    ["Baseline and failure classification (walkthroughs, Jun to Jul analysis validated, volumes and automation rate)", "A-D1", "1 to 2", by(2), "Items 5, 6, 15"],
    ["SAP interfaces, order method options, incompletion log, field mapping confirmed", "A-D3 (SAP part)", "1 to 2", by(2), "Item 9, SAP team"],
    ["Prototype in Dev: A2, A3, A4 on historical data", "A-D5 (prototype)", "1 to 2", by(2), "Sample, data approval, Model Armor"],
    ["Interim review", "A-D4", "2", "week of " + mon(2), "Steering attendance"],
    ["Exception map and order format analysis", "A-D2", "1 to 3", by(3), "Prototype results"],
    ["Target architecture incl. validation-location recommendation", "A-D3", "1 to 3", by(3), "Items 16 to 18"],
    ["Backtest report on 500 POs with proposed thresholds", "A-D5 (report)", "2 to 3", by(3), "Reference results confirmed by " + fri(2)],
    ["Business case and pilot plan; executive readout", "A-D6, A-D7", "2 to 3", by(3), "Item 7"],
    { band: "Stage 2" },
    ["Requirements and acceptance criteria for A1 to A10 and the business rules", "A-D8", "4 to 5", by(5), "Gate 1 decisions"],
    ["Solution design (steps, reviewer queue, cohort routing, observability, audit, retention)", "A-D9", "4 to 5", "submit by " + mon(5) + " so the 5-day review ends by " + fri(5), "Item 23 (retention)"],
    ["Integration specification (Salesforce, SAP reads, order API or BAPI, incompletion log, Graph, manual queue)", "A-D10", "4 to 5", "submit by " + mon(5), "Accenture, NTT Data, Infosys availability"],
    ["Environment and deployment design; test and evaluation plan", "A-D11, A-D12", "4 to 5", by(5), "Item 26 (standards and tools)"],
    { band: "Stage 3" },
    ["Dev environment completed and pipelines", "A-D13", "6 to 7", by(7), "Repository, deployer account"],
    ["Agent part 1: A1 to A4", "A-D14", "6 to 8", by(8), "Christmas week capacity"],
    ["Salesforce and Graph connectors, tested in Dev", "A-D15", "6 to 9", by(9), "Items 12, 13, 14"],
    ["Agent part 2: A5 to A7 (incl. reviewer queue)", "A-D14", "7 to 9", by(9), "Item 9 reads"],
    ["Evaluation suite on every build", "A-D16", "6 to 10", by(10), ""],
    ["SAP connectors (reads, order API or BAPI, incompletion log) against non-production SAP or stubs", "A-D15", "7 to 10", by(10), "Item 10, Gate 2 method"],
    ["Agent part 3: A8 to A10; audit and retention rules", "A-D14", "8 to 10", by(10), ""],
    ["Dashboards and alerts; build documentation, baseline and developer test cases", "A-D16, A-D16a/b/c", "8 to 10", by(10), ""],
    ["Reviewer screen usable for UAT", "part of A-D14 / A-D17", "8 to 10", by(10), "SSO decision"],
    { band: "Stage 4" },
    ["Test environment connected to non-production SAP and Salesforce", "A-D17", "11", by(11), "Test project (Stage 3)"],
    ["SIT and evaluation on unseen cases", "A-D18", "11 to 13", by(13), ""],
    ["Security testing per 5.4 and report; performance test; UAT support", "A-D19", "11 to 13", by(13), "UAT users nominated"],
    ["Release notes, go-live checklist, rollback rehearsal, run model", "A-D20", "12 to 13", by(13), "Item 27 (run owner, AMS partner)"],
    { band: "Stage 5 and 6" },
    ["Production deployment under change management", "A-D21", "14", by(14), "Prod project, change ticket"],
    ["Shadow mode run and report", "A-D22", "14 to 15", by(15), ""],
    ["Reviewer onboarding; assisted mode run and report", "A-D23", "15 to 17", by(17), "Cohort routed; reviewers available"],
    ["Hyper care weekly reports", "A-D24", "18 to 21", by(21), ""],
    ["Runbook, reviewer guide, KT sessions, reverse shadowing, KT sign-off", "A-D25", "16 to 21", by(21), "AMS partner available"],
    ["Closure report", "A-D26", "21 to 22", by(22), ""],
  ];
  return [
    H1("4. Timeline and deadlines"),
    P("Both agents start together in Week 0. Agent A runs 18 weeks including Week 0 to production acceptance at Gate 5, then four weeks of hyper care and closure at Gate 6 in week 22 (SOW 1.3, 7.0). The durations of Stages 2 to 5 are confirmed at Gate 1; a change goes through change control (4.1)."),
    H2("4.1 Stages and gates"),
    T(["Stage", "Weeks", "Dates", "Gate", "Decided by and criteria (SOW 4.2)"], stages, [2.3, 1, 2.6, 1.8, 3.8]),
    H2("4.2 Component deadlines (from the WBS of 23 October 2026)"),
    P("The build window is the WBS's planned span; \"done by\" is the Friday of its last week. A component that depends on an Ingredion input inherits that input's lateness day for day, which is why the dependency column exists."),
    T(["Component", "Deliverable", "Weeks", "Done by", "Depends on"], comps, [4, 1.6, 1, 2.2, 2.4]),
    H2("4.3 Calendar risks already visible"),
    UL([
      "**Diwali, Friday 6 November (week 1):** a non-working day for the Pune team in the first prototype week.",
      "**Thanksgiving, 26 and 27 November (week 4):** Ingredion is away for two of the ten working days of Stage 2, and Gate 2 needs the architecture and security review complete by " + g2 + ". Submit A-D9 and A-D10 by Monday " + mon(5) + " at the latest; better, walk Ingredion through drafts in week 4.",
      "**Christmas and New Year (weeks 8 and 9):** the middle of Stage 3. The WBS already plans reduced capacity; keep A-D14 part 1 ahead of schedule in weeks 6 and 7.",
      "**Gate 3 on " + g3 + ":** the first working week after the holidays. The documentation and test cases (A-D16a/b/c) are gate criteria, so write them during the build, not after.",
      "**Every Ingredion period is 5 working days** (reviews, decisions, access requests, UAT sign-off, production approval). Raise each request early in the week and log it in the RAID log the same day.",
    ]),
  ];
}

// ── section 8: steps ─────────────────────────────────────────────────────────
function stepBlock(title, rows) {
  return [H2(title), T(["", ""], rows, [1.6, 8.4])];
}
function steps() {
  const d1 = by(8), d2 = by(9), d3 = by(10), proto = by(2);
  return [
    H1("8. Build the steps A1 to A10"),
    P("The step contract is fixed: every module exposes `run(case, ctx) -> StepResult`, reads what it needs from `case.data`, writes typed results back, raises flags only through reason codes, and returns one of the dispositions CONTINUE, RETRY, REVIEW, EXIT or DONE (`factory/case.py`). The pipeline in `order_intake_agent/pipeline.py` owns the order of steps, the state machine (`factory/intake/state_machine.py`), parking for review, resuming after a decision, the write-ahead submit and the reconciliation on restart. You change steps and connectors; you rarely change the pipeline."),
    P("Build order: the Stage 1 prototype needs A2, A3 and A4 against historical data (" + proto + "); Stage 3 then builds A1 to A4 (" + d1 + "), A5 to A7 (" + d2 + ") and A8 to A10 (" + d3 + ") as the WBS splits A-D14."),
    CODE(`# Every step looks like this (order_intake_agent/steps/a2_classify.py, shortened)
STEP = "A2"
PROMPT = ("order_intake/a2_classify", 2)

def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    source = gather_source_text(case, ctx)                 # email + attachments through the layout readers
    try:
        result = call_model(ctx, PROMPT, {...}, Classification)
    except GuardBlocked as exc:
        case.add_flag("GUARD.BLOCKED", str(exc)); return StepResult.review("GUARD.BLOCKED")
    classification = result.value
    if classification.intent in NOT_AN_ORDER:
        return StepResult.exit(f"NOT_ORDER.{classification.intent.upper()}", note=classification.reason)
    case.data["classification"] = classification
    return StepResult.ok()`),
    ...stepBlock("A1 Pick up the case (`steps/a1_pickup.py`, `factory/intake/poller.py`, `factory/intake/claims.py`)", [
      ["Purpose", "Take each email order case from the queue exactly once, mark it as the agent's, and load the original email body and attachments from the case (SOW 2.3 A1)."],
      ["Today", "The `Poller` fetches new cases from a `CaseQueue`, checks the kill switch, claims each case in the `ClaimRegistry` (in-memory or Mongo, keyed `CASE:PO`) and dispatches it; A1 sets the Salesforce status to `agent_in_progress` through `SalesforceCases.set_status`. All against `StubCaseQueue` and `StubSalesforce`."],
      ["Build", "1. Implement `CaseQueue.fetch_new(after)` on Salesforce (section 9.1): the agent queue, the cohort filter, a `LastModifiedDate` watermark persisted in the case store. 2. Implement `SalesforceCases.get_email`: the `EmailMessage` under the case, each `ContentVersion` downloaded as bytes with its MIME type into `EmailBundle.attachments`. 3. Write the claim as a field on the case (item 13) as well as in the registry, so the RPA and manual staff see it. 4. Expose `POST /api/intake/poll` in `app/` for Cloud Scheduler (5.4). 5. Handle the one real failure mode: a case picked up twice after a restart; `reconcile_in_flight()` already handles the SAP side, make the claim idempotent on the Salesforce side."],
      ["Codes", "KILL_SWITCH (intake stopped). A1 never exits a case."],
      ["Tests", "`tests/order_intake/test_oi_pipeline.py` has the poller and claim tests; add a recorded Salesforce response fixture with two attachments and an email without a PDF."],
      ["Done by", d1 + " (prototype uses fixtures; the real queue needs items 12 and 13)"],
    ]),
    ...stepBlock("A2 Classify the email (`steps/a2_classify.py`, prompt `a2_classify.v2.md`)", [
      ["Purpose", "Decide what the email is before anything else runs: new order, revised PO, duplicate, change, cancellation, inquiry, credit memo or other; language; handwritten; the PO numbers; whether the email holds more than one PO (SOW 2.3 A2, 2.4)."],
      ["Today", "Prompt v2 returns the `Classification` schema (intent, po_numbers, language, handwritten, confidence). Exits NOT_ORDER.*, FORMAT.NON_ENGLISH and FORMAT.HANDWRITTEN; flags EMAIL.REVISED_PO, EMAIL.DUPLICATE_SUBMISSION, EMAIL.MULTI_PO. In fallback mode the recorded RPA error can route a case without a model call."],
      ["Build", "1. Classify per attachment as well as per email: the failure analysis shows 84 cases where the RPA ran a terms-and-conditions PDF as a PO; a `document_role` per attachment (purchase_order, terms, other) keeps A3 on the right file. 2. Multi-PO handling: today the email is flagged; build child cases so N orders can sit on one Salesforce case with partial success (decision due at Gate 2, " + g2 + "). 3. Calibrate on the backtest: measure intent accuracy per Customer and set the confidence below which A2 sends the case to the reviewer instead of exiting. 4. Try `gemini-2.5-flash` for this step once accuracy is known; it is the cheapest call to downgrade."],
      ["Codes", "NOT_ORDER.*, FORMAT.NON_ENGLISH, FORMAT.HANDWRITTEN, EMAIL.MULTI_PO, EMAIL.REVISED_PO, EMAIL.DUPLICATE_SUBMISSION, GUARD.BLOCKED."],
      ["Tests", "`a2_with(...)` in `oi_fixtures.py` builds a fake answer; add the terms-attachment case and a French PO."],
      ["Done by", "Prototype " + proto + "; final " + d1],
    ]),
    ...stepBlock("A3 Read the PO (`steps/a3_extract.py`, prompt `a3_extract.v1.md`, `factory/model_gateway/document_ai.py`)", [
      ["Purpose", "Extract the order: Customer, PO number, dates, ship-to and bill-to, lines with Customer material, SAP material if printed, quantity, unit, price, line totals and grand total, each with a confidence (SOW 2.3 A3)."],
      ["Today", "`POExtraction` schema; `gather_source_text` runs the attachments through the `CompositeReader` (plain text, Excel, Word, Document AI, legacy Azure) and the prompt gets the text; one re-read with hints after an `ExtractionFormatError`; `CompositeConfidence` combines model, layout, arithmetic, master-data and history evidence."],
      ["Build", "1. Multimodal route for digital PDFs and images (6.3) and the Document AI route for scans (section 7); choose per document from the Stage 1 sample and record the route and the mean confidence in the audit record. 2. Excel and Word POs through the readers (install openpyxl and python-docx in the image). 3. The arithmetic check (line totals against the grand total) feeds confidence, it does not fail the case; 133 of the RPA's failures were this check. 4. Zero and ambiguous quantities: read quantity and unit together and never divide by SAP bag weight (96 RPA failures). 5. Dates in ISO form in the schema whatever the PO prints (54 RPA failures). 6. Field-level accuracy harness against the final SAP orders for every prompt change (section 13)."],
      ["Codes", "EXTRACT.REREAD, EXTRACT.FORMAT_ERROR, EXTRACT.LOW_CONFIDENCE, EXTRACT.NO_LINES, EXTRACT.ZERO_QUANTITY, EXTRACT.LINE_TOTALS_MISMATCH, EXTRACT.NOT_NUMERIC, EXTRACT.DATE_FORMAT, EXTRACT.PO_NUMBER_MISSING, FORMAT.UNREADABLE, GUARD.BLOCKED."],
      ["Tests", "`a3_with(...)` fixtures; add one real-layout sample per top Customer from the backtest set as golden files (Batory, Ken's Foods, Sweets Mix, IFF, Kerry Ingredients) once Ingredion approves their use in tests."],
      ["Done by", "Prototype " + proto + "; final " + d1],
    ]),
    ...stepBlock("A4 Map to SAP fields and validate (`steps/a4_validate.py`)", [
      ["Purpose", "Resolve sold-to, ship-to and bill-to and the material against SAP master data including CMIR, convert quantities to the SAP sales unit, with no mapping database (SOW 2.3 A4, 2.4)."],
      ["Today", "`SAPMasterData.find_partner`, `cmir`, `uom_conversion` and `allowed_uoms` through stubs; exits MASTER.*_NOT_FOUND; CMIR candidates and ambiguous units go to review; corrections from the reviewer re-run the step (`revalidate_after_correction`)."],
      ["Build", "1. Implement `SAPMasterData` against the interface Ingredion confirms (A-D3 by " + fri(2) + "): either SAP reads through API Management or the SAP data already in Google Cloud (SOW 2.5; the validation location is decided at Gate 1, " + g1 + "); write both as thin clients behind the same protocol so the decision is a configuration choice. 2. Ship-to disambiguation from the PO address when several CMIR records match (119 RPA failures). 3. Customer resolution by name and address when the PO carries no SAP numbers (the RPA needed a per-customer model; 14 failures). 4. Measure in Stage 1 how many of the 277 \"material not available\" cases exist in SAP CMIR; those are the ones A4 resolves, the rest are reported (SOW 8.2(a))."],
      ["Codes", "MASTER.SOLD_TO_NOT_FOUND, MASTER.SHIP_TO_NOT_FOUND, MASTER.BILL_TO_NOT_FOUND, MASTER.MATERIAL_NOT_FOUND, MASTER.PARTNER_AMBIGUOUS, CMIR.MULTIPLE_MATCHES, UOM.NO_CONVERSION, UOM.INVALID, UOM.AMBIGUOUS."],
      ["Tests", "Master-data fixtures in `StubSAPMasterData`; add the CMIR-multiple and the TON-ambiguity cases from the sample."],
      ["Done by", "Prototype on extraction output " + proto + "; real reads when item 9 lands; final " + d1],
    ]),
    ...stepBlock("A5 Rules and confidence (`steps/a5_score.py`, `factory/rules/confidence.py`)", [
      ["Purpose", "Price against SAP pricing and the contract, availability (ATP, allocation, restricted products, volume commitments), duplicate orders, composite confidence; mismatches flagged to the reviewer (SOW 2.3 A5, 2.4)."],
      ["Today", "`SAPOrders.price`, `contract`, `availability`, `find_duplicates` (30-day window) through stubs; flags PRICE.PO_VS_SAP, CONTRACT.*, ATP.SHORT, ALLOC.EXCEEDED, PRODUCT.RESTRICTED, DUP.POSSIBLE; the composite score and `confidence_threshold` 0.80; recheck mode after corrections."],
      ["Build", "1. Real reads through the confirmed interface. 2. The MAX load quantity check as a FLAG (QTY.MAX_LOAD, new code; 32 RPA failures). 3. Threshold calibration from the backtest; the thresholds are a Gate 1 decision, so keep them in configuration, not code. 4. Duplicate detection against existing SAP orders by PO number, sold-to, ship-to, material, date and quantity (157 RPA failures were resubmissions); a confirmed duplicate closes the case without an order."],
      ["Codes", "PRICE.PO_VS_SAP, CONTRACT.NONE, CONTRACT.OUTSIDE_TERMS, ATP.SHORT, ALLOC.EXCEEDED, PRODUCT.RESTRICTED, QTY.MAX_LOAD, DUP.POSSIBLE, DUP.CONFIRMED."],
      ["Tests", "`StubSAPOrders` scenarios; add a price-stale and a duplicate-within-window case."],
      ["Done by", d2],
    ]),
    ...stepBlock("A6 Exceptions (`steps/a6_exceptions.py`, prompt `a6_exceptions.v1.md`)", [
      ["Purpose", "Draft the Customer clarification for missing data, price mismatch, invalid material or a revised PO, for the reviewer to send; unresolved exceptions leave to the manual queue (SOW 2.3 A6)."],
      ["Today", "Flags with Customer-facing prefixes (PRICE., CONTRACT., ATP., UOM., EXTRACT.LOW_CONFIDENCE) produce a `ClarificationDraft` (to, subject, body, reasons) from Gemini, with a template fallback; `GraphMail.create_draft` saves it in the shared mailbox and the draft id is stored on the case."],
      ["Build", "1. The Graph connector (9.3) with draft-only permission. 2. Screen the draft with Model Armor's response filter before it is saved. 3. The draft text also sits on the review item, so a Graph outage never blocks the reviewer. 4. Reviewer sends from Outlook; the agent never sends (SOW 10.2)."],
      ["Codes", "EXCEPTION.UNRESOLVED (exit), GUARD.BLOCKED."],
      ["Tests", "`a6_with(...)` fixture; `StubGraphMail.drafts` assertions."],
      ["Done by", d2],
    ]),
    ...stepBlock("A7 Review summary and the human gate (`steps/a7_review_summary.py`, `factory/review/`)", [
      ["Purpose", "Summarise the order with the doubtful fields highlighted and stop every case at the reviewer in Phase 1; approve, correct or reject (SOW 2.3 A7 and the human judgment gate)."],
      ["Today", "`build_review_item` creates a `ReviewItem` with the fields, flags, candidates and drafts; the pipeline parks the case (`_park`) and `resume(case, decision)` continues it: approve goes to A8, correct applies the corrections and re-runs A4 and A5 (REVIEW.RECHECK_FLAGGED if new flags appear), reject returns the case (REVIEW.REJECTED), a confirmed duplicate closes it. The REST router serves the queue; `on_decision` wires decisions to the pipeline."],
      ["Build", "The reviewer screen and identity (section 10). Keep `review_every_case = True`; Phase 2 is a Gate 5 decision and becomes a policy change, not a code change."],
      ["Codes", "REVIEW.REJECTED, REVIEW.CORRECTED, REVIEW.RECHECK_FLAGGED, DUP.CONFIRMED."],
      ["Tests", "Resume paths are covered in `test_oi_pipeline.py` and `test_review_ops_api.py`; add a decision by the wrong user (must be refused)."],
      ["Done by", "API now; screen usable " + d3 + "; polished for UAT by " + fri(11)],
    ]),
    ...stepBlock("A8 Build the SAP payload (`steps/a8_build_payload.py`)", [
      ["Purpose", "Build the same payload the RPA builds, from validated, enriched and, where applicable, corrected data (SOW 2.3 A8)."],
      ["Today", "`SAPPayload` and `SAPItem` models assembled from the validated lines and the sold-to."],
      ["Build", "1. Field-level parity with the RPA payload from the SAP field requirements and mapping Ingredion provides (items 8 and 10) and the 10 to 20 sample payloads: write them as golden tests. 2. Partner functions, pricing date, requested delivery date, incoterms and texts as the mapping dictates. 3. Keep the payload serialisable and stored on the case before A9 runs (it is the write-ahead record)."],
      ["Codes", "None of its own."],
      ["Tests", "Golden payload tests from the samples; a property test that every validated line appears exactly once."],
      ["Done by", d3],
    ]),
    ...stepBlock("A9 Create the order (`steps/a9_create_order.py`)", [
      ["Purpose", "Create the sales order by the method approved at Gate 2, confirm it was created, then read the incompletion log and capture anything that could block downstream processing (SOW 2.3 A9, 2.4)."],
      ["Today", "Write-ahead `submitting` state with the idempotency key `CASE:PO`; `find_by_reference` lookup before the first attempt and before every retry; three retries with 2, 5 and 15 second waits; a pause after five consecutive failures; `reconcile_in_flight()` on restart; `incompletion_log` read into SAP.INCOMPLETE flags."],
      ["Build", "1. Implement `SAPOrderAPI` through API Management for the approved method (Gate 2, " + g2 + "): the error payloads in Ingredion's analysis show the RPA calls the SAP BAPI through a Logic Apps connector (SALES_HEADER_IN), so BAPI_SALESORDER_CREATEFROMDAT2 wrapped by APIM is the likely path; the SAP Order API is the alternative. 2. Ask APIM to carry the idempotency key as a header and reject a repeat; the lookup stays regardless. 3. Map SAP return messages to SAP.REJECTED (business error, exit) versus SAP.UNAVAILABLE (technical, retry). 4. Shadow mode: this step must be provably inert (14.1). 5. Incompletion log: the interface is confirmed in A-D3; map items to follow-ups A10 writes."],
      ["Codes", "SAP.REJECTED, SAP.UNAVAILABLE (exits), SAP.RECONCILED (info), SAP.INCOMPLETE (flag)."],
      ["Tests", "`StubSAPOrderAPI` scripts cover created, timeout_but_created, timeout, unavailable and rejected; keep them green against the real client's error mapping."],
      ["Done by", d3],
    ]),
    ...stepBlock("A10 Update the Salesforce case (`steps/a10_update_case.py`)", [
      ["Purpose", "Write the order number, status, incompletion results, required follow-ups and an audit note to the original case; complete it when nothing is outstanding (SOW 2.3 A10, 2.4 case continuity)."],
      ["Today", "`SalesforceCases.complete(case_id, order_numbers, outcome, note, follow_ups)` and `return_case` through the stub; outcomes AGENT_CREATED, AGENT_ASSISTED, RETURNED; `retry_case_update` retries A10 independently of A9 so a Salesforce outage never re-creates an order."],
      ["Build", "1. The field set and status values agreed with Ingredion (item 13): outcome marker, order numbers, reason codes, follow-up text, audit note. 2. Never create a second case or notification for the same PO (SOW 2.4). 3. Returned cases carry the reason code and the clarification draft reference for Customer Service."],
      ["Codes", "Outcome values AGENT_CREATED, AGENT_ASSISTED, RETURNED; SAP.INCOMPLETE follow-ups."],
      ["Tests", "`StubSalesforce.completed` and `.returned` assertions; add a retry after a 5xx."],
      ["Done by", d3],
    ]),
  ];
}

// ── section 9: connectors ────────────────────────────────────────────────────
function connectors() {
  return [
    H1("9. Connectors (A-D15)"),
    P("All connectors implement the protocols in `order_intake_agent/connectors/__init__.py`, so the steps and tests do not change when a stub is replaced. Put each real client in its own module (`connectors/salesforce.py`, `connectors/sap.py`, `connectors/graph.py`, `connectors/rpa_record.py`), construct them in `order_intake_agent/runtime.py` from settings, and keep the stubs for Dev and tests. Every outbound call is traced, timed and retried with a bounded policy; credentials come from Secret Manager."),
    H2("9.1 Salesforce (A1 and A10) · done by " + friD(9)),
    OL([
      "**Access.** Ingredion creates a connected app for the agent and an integration user with a permission set limited to the agent's needs: read `Case`, `EmailMessage`, `ContentDocumentLink`, `ContentVersion` on the email order queue; edit only the agent fields on `Case` (claim status, outcome marker, order numbers, reason codes, follow-up text). Use the OAuth 2.0 JWT bearer flow with a certificate (no passwords, no refresh tokens in storage); the private key lives in Secret Manager. Start in a sandbox (item 12).",
      "**Queue and routing (item 13).** Email order cases for the cohorts moved to the agent are assigned to an agent queue (or carry a cohort field); the agent reads only those. Routing a cohort to the agent, or back to the RPA, is a Salesforce change Ingredion makes by the Gate 2 dates (SOW 8.1(e)).",
      "**Reads.** `fetch_new(after)`: `SELECT Id, CaseNumber, AccountId, Subject, CreatedDate, LastModifiedDate FROM Case WHERE OwnerId = :queueId AND Agent_Claim__c = null AND LastModifiedDate > :after ORDER BY LastModifiedDate`. `get_email(case_id)`: the `EmailMessage` records for the case, then `ContentDocumentLink` to `ContentVersion` and the `VersionData` download for each attachment (bytes and MIME type into `EmailBundle`).",
      "**Writes.** Claim: update `Agent_Claim__c`, `Agent_Status__c` (A1). Completion: order numbers, outcome marker, follow-ups, audit note, and the case status Ingredion agrees (A10). Return: reason codes and note, status back to the manual queue value (A10 and exits). Field names are placeholders until item 13 is answered.",
      "**Limits and behaviour.** Respect the daily API request allocation (batch reads, no polling faster than every two minutes); page large queues; treat `INVALID_SESSION_ID` as a token refresh, not an error; log every write with the case id.",
      "**Tests.** Record real sandbox responses once and replay them in tests; keep `StubSalesforce` for the pipeline tests.",
    ]),
    H2("9.2 SAP through Azure API Management (A4, A5, A9) · interfaces confirmed by " + friD(2) + ", connectors done by " + friD(10)),
    P("The exact services are a Stage 1 confirmation with the SAP team (A-D3) and the order method is approved at Gate 2. Build the clients so that endpoints and payload mappings are configuration. Candidates to confirm, in the order the steps need them:"),
    T(["Need", "Protocol method", "Candidate interface", "Notes"], [
      ["Partners (sold-to, ship-to, bill-to) by number, name, address", "`SAPMasterData.find_partner`", "Business partner or customer master read service behind APIM", "Address matching needs the full address fields"],
      ["Customer-material info records", "`SAPMasterData.cmir`", "Customer material (CMIR) read service", "Several records per Customer material is the normal case; return all"],
      ["Units of measure", "`SAPMasterData.uom_conversion`, `allowed_uoms`", "Material master alternative units", "Conversion factors per material; never bag weight arithmetic in code"],
      ["Pricing and contract", "`SAPOrders.price`, `contract`", "Pricing simulation or condition record read; contract (quantity contract) read", "A simulate call gives the price SAP will actually use"],
      ["Availability", "`SAPOrders.availability`", "ATP check (availability, allocation, restricted products, volume commitments)", "Flags only; never changes the order"],
      ["Existing orders", "`SAPOrders.find_duplicates`, `find_by_reference`", "Sales order read by Customer PO number, sold-to, ship-to, material, date", "The lookup before any retry depends on the PO-number field being searchable"],
      ["Create the order", "`SAPOrderAPI.create_order`", "BAPI_SALESORDER_CREATEFROMDAT2 wrapped by APIM (the RPA's current path), or the SAP Order API", "Approved at Gate 2; idempotency key as a header; commit semantics confirmed"],
      ["Incompletion log", "`SAPOrderAPI.incompletion_log`", "Incompletion log read for a created order", "Interface confirmed in Stage 1 (SOW 2.5)"],
    ], [3, 2.4, 3, 3]),
    UL([
      "**Authentication:** APIM subscription key plus an OAuth 2.0 client-credentials token from Ingredion's Entra tenant; both in Secret Manager. The service account's identity does not cross the cloud boundary, so the APIM credential is the one the authorization test checks: it must have no rights beyond the listed operations.",
      "**If Gate 1 chooses validation in Google Cloud:** implement `SAPMasterData` and the read side of `SAPOrders` against the datasets Ingredion already loads (BigQuery or Cloud SQL), with their refresh times recorded on every case; A9 still writes through APIM.",
      "**Non-production SAP** (item 11) is what SIT uses; until it exists, the stubs and recorded responses carry the tests.",
    ]),
    H2("9.3 Microsoft Graph for the clarification draft (A6) · done by " + friD(9)),
    OL([
      "Ingredion registers an application in its Entra tenant with the application permission `Mail.ReadWrite`, restricted to the shared order mailboxes with an application access policy (`New-ApplicationAccessPolicy -AccessRight RestrictAccess`); no `Mail.Send` (item 14; SOW 10.2 forbids sending without reviewer approval). The SOW allows \"draft or send\"; we ask for draft only.",
      "Client-credentials token through MSAL; client secret or certificate in Secret Manager.",
      "`create_draft(mailbox, to, subject, body, case_ref)` is `POST /users/{mailbox}/messages` with the message body; Graph creates it as a draft. Store the returned id on the case and in the review item; the reviewer opens it in Outlook and sends.",
      "Test once against the test mailbox in Stage 2; the stub keeps the pipeline tests independent of Graph.",
    ]),
    H2("9.4 The RPA failure record (baseline and shadow comparison)"),
    P("Read access to the PurchaseOrder PDF table, the Power Automate run history and the OCR model configuration (item 15) serves two purposes: the Stage 1 baseline (A-D1) and the shadow-mode comparison (A-D22) where the agent's result is compared with what the RPA did on the same case. `FailureRecordReader` and `rpa_errors.classify_rpa_message` already handle the record format and the sixteen error types; wire a reader to the real table (SQL read or an extract to Cloud Storage) and keep it out of the production intake path. The RPA stays deployable until Ingredion retires it; falling back to it is the Salesforce routing change in reverse."),
  ];
}

// ── section 10: review screen ────────────────────────────────────────────────
function reviewScreen() {
  return [
    H1("10. The human gate: review queue and reviewer screen"),
    P("The SOW places the human judgment gate inside the agent: A7 builds the review summary and the reviewer works a queue (SOW 2.3, redline diagram \"Human gate · review queue\"), and the result is written back to the Salesforce case at A10. So the accept, correct or reject screen is ours to build; Salesforce write access is needed for A10 in any event. This answers the question raised with the team on 23 October."),
    H2("10.1 What exists"),
    UL([
      "`GET /api/review/items`, `GET /api/review/items/{id}`, `POST /api/review/items/{id}/decision` (`factory/review/router.py`), mounted in `app/main.py` with `on_decision` wired to `pipeline.on_decision`.",
      "`ReviewItem` carries the case id, the extracted fields with flags and candidates, the reason codes, the clarification draft and the Outlook draft id; `Decision` is approve, correct (with corrections per field) or reject (reason required, 422 otherwise); a second decision on the same item returns 409.",
      "Identity today is an API key plus an `X-User-Id` header: a stand-in for Dev only.",
    ]),
    H2("10.2 What to build (usable by Gate 3, " + g3 + "; hardened for UAT by " + friD(11) + ")"),
    OL([
      "**A small web application on Cloud Run** behind Identity-Aware Proxy with Ingredion's identity provider (Entra ID or Google Workspace, whichever Ingredion runs), so the reviewer's identity reaches the audit trail from the IAP header rather than from a client-supplied value. Replace `app/auth.py`'s stand-in with that identity when IAP is in front; keep the API key for machine calls.",
      "**Screens:** the queue by cohort and age; one case with the PO rendered on the left and the extracted fields on the right, doubtful fields highlighted with the reason code and the candidates (for CMIR and partners) as choices; price, contract, availability and duplicate flags with the SAP values beside the PO values; the clarification draft with an \"open in Outlook\" link; approve, correct (edit fields, pick candidates) and reject (reason) buttons.",
      "**Behaviour:** a correction re-runs A4 and A5 and shows new flags before the reviewer approves (`REVIEW.RECHECK_FLAGGED`); a confirmed duplicate closes the case; the reviewer never edits the SAP payload directly.",
      "**Alternative if Ingredion prefers Salesforce:** a Lightning component calling the same API from the case page. More Salesforce work for Ingredion, so decide it in Stage 2 (A-D9).",
      "**Reviewer guide:** draft for onboarding in week 15 (A-D23), final in A-D25.",
    ]),
  ];
}

// ── section 13: testing and the backtest ─────────────────────────────────────
function testing() {
  return [
    H1("13. Testing, evaluation and the Stage 1 backtest"),
    H2("13.1 Unit tests and the harness"),
    UL([
      "`tests/order_intake/oi_fixtures.py` builds a complete runtime with stubs and `FakeStructuredExtractor` (`build(a2=..., a3=..., a6=..., api_script=..., policy=...)`); `make_case`, `make_email`, `A2_OK`, `A3_OK`, `A6_OK` are the ready-made answers. Every new behaviour gets a pipeline-level test here and a unit test in its module.",
      "Mongo paths run on mongomock; the Vertex, Document AI and Model Armor adapters have fake clients in `tests/factory/test_gcp_adapters.py`; keep those fakes in step with the real SDK calls you add.",
      "Run `pytest -q` and `ruff check .` before every push; the pipeline runs them again (section 12).",
    ]),
    H2("13.2 The evaluation suite (A-D16)"),
    P("`factory/evaluation/order_intake.py` scores a set of cases: a `Prediction` per case (fields, confidence, flags) against an `Answer` (the final SAP order), over `KEY_FIELDS`, and reports field-level accuracy, undetected errors and recovery against `GATE_THRESHOLDS` (`gate1`, `gate4`, `phase2`). Make it part of every build: a fixed evaluation set of approved historical cases in the Dev bucket, run with the fake model in CI and with the real model nightly in Dev; a drop against the released version blocks the release."),
    H2("13.3 The Stage 1 backtest, step by step (A-D5 report by " + friD(3) + ")"),
    OL([
      "**Receive the sample (by 2 November 2026, item 5):** 500 past email POs including RPA-failed POs, with attachments, RPA and OCR output, failure reasons and the final SAP orders. Load it into `ingredion-oi-samples-dev` with one folder per case and a manifest (case id, Customer, ship-to, date, RPA outcome, SAP order number).",
      "**Label it:** run `order_intake_agent.rpa_errors.classify_rpa_message` over the RPA messages to tag each failed case with its error type and the agent step that absorbs it; split the sample by Customer, ship-to and failure type; check it represents the June to July mix (Ingredion's workbook is the reference).",
      "**Get the answer key confirmed (by " + friD(2) + "):** Ingredion confirms the final SAP orders are correct (8.1(c)); without that the accuracy numbers are not defensible.",
      "**Run the prototype (by " + friD(2) + "):** A2, A3 and A4 in Dev against the real model, with Model Armor on and Document AI for scans; store every `StructuredResult` and `LayoutResult` so the run can be re-scored without re-calling the model.",
      "**Score:** field-level accuracy and undetected errors per key field, per Customer and per RPA failure type; the share of RPA failures the agent would have completed; the routing table (Document AI, Gemini direct, Excel, Word) with mean confidence per route; guard block rate; tokens, pages and latency per case for the run-cost estimate.",
      "**Propose thresholds:** for Phase 1 review and Phase 2 automation from the confidence distribution against the errors actually found; and the completion-rate target per cohort against the RPA's rate from the baseline (A-D1).",
      "**Write A-D5** with the method, the numbers and the recommendation on validation location; present at the executive readout in the week of " + mon(3) + ".",
    ]),
    H2("13.4 Stage 4: SIT, unseen-case evaluation, UAT, performance (" + mon(11) + " to " + fri(13) + ")"),
    UL([
      "SIT in the Test project against non-production SAP and Salesforce (A-D17 by " + friD(11) + "): end to end from a case in the sandbox queue to an order in non-production SAP and the case update; defects fixed as found (A-D18 by " + friD(13) + ").",
      "Evaluation on historical cases not used during build, reported per key field against the Gate 1 thresholds (A-D18).",
      "UAT by Ingredion business users from the week of " + mon(12) + "; nominate users and reviewers by Stage 3; sign-off within 5 working days of completion (8.1(e)).",
      "Performance test in the week of " + mon(12) + " at expected volumes: the error analysis implies about 2,000 cases a month, so plan for 100 to 150 cases a day with bursts when the bot batches run; measure latency per step, model quota headroom and queue age.",
      "Security testing and the 5.4 report (A-D19), the rollback rehearsal and the run model (A-D20) complete the Gate 4 pack (" + g4 + ").",
    ]),
  ];
}

// ── section 15: deliverables ─────────────────────────────────────────────────
function deliverables() {
  const rows = [
    { band: "Stage 1 (weeks 1 to 3; Gate 1 " + g1 + ")" },
    ["A-D1", "Baseline and failure classification", by(2)], ["A-D2", "Exception map (failure types and causes, order format analysis, master-data and SAP findings)", by(3)],
    ["A-D3", "Target architecture (GCP, integration points, field-mapping approach, security, audit, monitoring; validation-location recommendation)", by(3)], ["A-D4", "Interim review session", "week of " + mon(2)],
    ["A-D5", "Prototype and backtest report with proposed thresholds", "prototype " + by(2) + "; report " + by(3)], ["A-D6", "Business case and pilot plan", by(3)], ["A-D7", "Executive readout", "week of " + mon(3)],
    { band: "Stage 2 (weeks 4 to 5; Gate 2 " + g2 + ")" },
    ["A-D8", "Requirements and acceptance criteria", by(5)], ["A-D9", "Solution design document", "submit " + mon(5)], ["A-D10", "Integration specification", "submit " + mon(5)], ["A-D11", "Environment and deployment design", by(5)], ["A-D12", "Test and evaluation plan", by(5)],
    { band: "Stage 3 (weeks 6 to 10; Gate 3 " + g3 + ")" },
    ["A-D13", "Dev environment completion and pipelines", by(7)], ["A-D14", "Agent (A1 to A4 " + by(8) + "; A5 to A7 " + by(9) + "; A8 to A10 " + by(10) + ")", by(10)], ["A-D15", "Integration components (Salesforce and Graph " + by(9) + "; SAP " + by(10) + ")", by(10)],
    ["A-D16", "Evaluation suite, build test report, monitoring dashboards and alerts", by(10)], ["A-D16a", "Technical build documentation incl. third-party and open-source list", by(10)], ["A-D16b", "Baseline test cases Ingredion can expand for SIT and UAT", by(10)], ["A-D16c", "Developer test cases with results", by(10)],
    { band: "Stage 4 (weeks 11 to 13; Gate 4 " + g4 + ")" },
    ["A-D17", "Test environment connected to non-production SAP and Salesforce", by(11)], ["A-D18", "SIT and evaluation report (unseen cases)", by(13)], ["A-D19", "UAT, performance and security report (5.4 findings closed)", by(13)], ["A-D20", "Release readiness pack: release notes, deployment and rollback plan (rehearsed), open defects, go-live checklist, run model", by(13)],
    { band: "Stage 5 (weeks 14 to 17; Gate 5 " + g5 + ")" },
    ["A-D21", "Production deployment", by(14)], ["A-D22", "Shadow mode report", by(15)], ["A-D23", "Assisted mode report (incl. reviewer onboarding)", by(17)],
    { band: "Stage 6 (weeks 18 to 21; Gate 6 " + g6 + ")" },
    ["A-D24", "Hyper care report (weekly)", by(21)], ["A-D25", "Runbook, reviewer guide, knowledge transfer, Knowledge Transition plan and sign-off record", by(21)], ["A-D26", "Closure report", by(22)],
  ];
  return [
    H1("15. Deliverables checklist with dates"),
    P("Each deliverable is submitted with a short cover note (what it contains, which agent and stage); Ingredion reviews within 5 working days and silence is acceptance (SOW 4.2, 9.0). Document deliverables are in Microsoft Office formats or PDF, in English (8.2(c)). Keep every deliverable in the repository under `docs/deliverables/` so Gate 6's \"all work product in Ingredion's repository\" is true by construction."),
    T(["ID", "Deliverable (SOW 2.6)", "Done by"], rows, [1, 6, 3]),
  ];
}

module.exports = { agent, whatYouBuild, timeline, steps, connectors, reviewScreen, testing, deliverables };
