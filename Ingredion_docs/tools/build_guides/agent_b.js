// Agent B: Pre-bill Validation and Dispute Prevention Agent.
const { H1, H2, H3, P, UL, OL, T, CODE, NOTE, mon, fri, friD, by, span } = require("./lib");

const g1 = friD(3), g2 = friD(5), g3 = friD(9), g4 = friD(12), g5 = friD(15), g6 = friD(20);

const agent = {
  letter: "B", name: "Agent B, the Pre-bill Validation and Dispute Prevention Agent", short: "Agent B", pkg: "prebill_agent",
  steps: "B1 to B8", delivSection: "3.7", processSection: "3.3", scorecardSection: "3.4",
  writes: "B7 and B8 write, and only to the agent's own review queue and audit trail; Agent B writes to no Ingredion system (SOW 8.2(a)). So the rule here is: nothing",
  saName: "prebill-agent", service: "ingredion-prebill",
  pollCall: "the pre-bill pick-up (B1 over `SAPBilling.list_ready(after)`, then `pipeline.process(ref)` per order)",
  envExtra: "EXTRACT_BUCKET=ingredion-pb-extracts-dev",
  networkIntro: "Agent B reads six sources, several of them outside Google Cloud: SAP through Azure API Management, PROS, Salesforce, Ariba, TermSync and the contract and fuel-rate files.",
  modelSteps: "B3 (reading the Customer PO) and B6 (explaining each gap and drafting the PO-update request)",
  promptDir: "prebill", promptFiles: "`b3_read_po.v1.md`, `b6_explain.v1.md`",
  outputGuard: "the B6 explanation and the drafted PO-update request", docAIStep: "B3",
  g3, g4, g5, g6, stage3End: 9, evalCmd: "prebill", evalNote: "runs the Kraft Heinz anchor and the clean and converted-unit worlds; must report 4/4 caught, no false alarms",
  authzTest: "prove the account and the APIM credential have no write permission on SAP, PROS, Salesforce, Ariba or TermSync (a write attempt must be refused by the system, not just avoided by the code).",
  dashboardMetrics: "catch rate, false alarms, missing-data cases, traceability, reviewer agreement, review queue age and time to decision, cases per outcome, guard blocks, tokens and pages per case, run cost (SOW 3.3 and 3.4).",
  shadowSpan: span(13, 13), assistedSpan: span(14, 15), hyperSpan: span(16, 19), ktSpan: span(17, 18), reverseSpan: span(18, 19), closureSpan: span(19, 20),
  shadowText: "Deploy to Prod under Ingredion change management with read-only access (B-D21, by " + friD(13) + "). In the single shadow week the agent checks live invoice-ready orders but routes nothing to owners; its outcomes are compared with what happened to the same invoices (accepted, rejected by the portal, short-paid, disputed) and the variances and prompts are tuned through release approval. One week is short, as the WBS notes, so the comparison harness must exist before Gate 4 and the first comparison runs on the Monday.",
  assistedText: "Every case that is not Matched goes to the named owner through the review queue and the notification channel confirmed in Stage 2; the owner confirms or overrides the outcome, sends the PO-update request or corrects the Ingredion side; overrides are captured for tuning. The agent still writes to nothing outside its queue and audit trail. Owner onboarding (B-D23, week of " + mon(13) + ") comes first; medium security findings close or get dates in this window.",
  gate5Decision: "At the same gate Ingredion decides whether to extend the agent to other dispute types (4.2).",
  closureEvidence: "the evidence for Ingredion's decision on later dispute types",
  week0ParkarExtra: "Agree with Ingredion the number of past orders in the backtest sample (the WBS puts this in Week 0) and raise the access requests for the six source systems and the extracts.",
  baseline: [
    ["Steps B1 to B8", "Step modules, pipeline with `process`, `resume` and `recheck`, fixtures for the Kraft Heinz anchor, a clean world and a converted-units world; tests", "Real inputs through the connectors; the invoice-ready signal; prompts tuned on the sample; owner flow end to end"],
    ["Rules and normalisation", "`UnitPriceRule`, `FreightRule`, `FuelSurchargeRule`, `QuantityRule`, `PaymentTermsRule`; outcomes and owners per outcome; unit (CWT, lb, kg) and currency conversion; line pairing", "Ingredion's variances and source-wins rule as configuration (Gate 1); material factors and rate tables from the real files"],
    ["Model gateway", "Shared with Agent A: `VertexStructuredExtractor`, `PromptRegistry`, `GuardedExtractor`, `ModelArmorGuard`; prompts b3 v1, b6 v1", "First real Gemini calls for B3 and B6; multimodal PO reading; response screening of the draft"],
    ["Connectors", "Read-only protocols and Dev stubs for SAP billing, PROS, Salesforce orders, Ariba, TermSync, rate files, mailbox; `GcsExtractLanding` for scheduled extracts", "Six real read clients or extract loaders (section 9)"],
    ["Human gate", "Review queue and REST router shared with Agent A; B7 routes to the owner per outcome", "Owner screen or notification channel, SSO identity, owner guide"],
    ["Operations", "Kill switch, ops router, OpenTelemetry to Cloud Trace, append-only audit trail, reason-code catalogue", "Dashboards and alerts for the 3.4 scorecard, retention jobs, runbook, Cloud Run deployment, pipelines, the 5.4 tests"],
    ["Evaluation", "`score_prebill` with the anchor case (4 of 4) and verdict bands; `python -m factory.evaluation prebill`", "The backtest on Ingredion's sample of past orders; SIT and UAT evidence; scorecard reporting from the audit trail"],
  ],
  week0Deps: [
    ["Named leads, Project Manager, Agent B SMEs: Pricing and Billing, AR and Collections, Customer Service, SAP, PROS, Salesforce (items 1, B6)", "Sponsor, technical lead", "Before " + mon(0), "Book the weekly status, the interim review (week of " + mon(2) + ") and the executive readout (week of " + mon(3) + "); schedule the invoice-ready to invoice-sent walkthrough."],
    ["Sample of past invoiced orders in the number agreed in Week 0, incl. Kraft Heinz SO 809-6862, with the Customer PO, SAP order, delivery and billing data and the dispute or payment outcome; correct outcome confirmed per case (item B1)", "Agent B use-case lead; Pricing and Billing", "Within 5 working days of " + mon(0) + " (by 2 Nov 2026); outcomes confirmed by " + fri(2), "Land it in the samples bucket as one folder per order; build the test-case set (B-D2); record the Stage 1 start date in the RAID log."],
    ["Read access or scheduled extracts: SAP order, delivery, billing, pricing, freight; PROS; Salesforce cases and PO documents; Ariba POs; TermSync; contract and fuel-rate files (item B2)", "Technical lead; system owners", "Week 0 to week 1", "For each source decide read interface or extract (B-D3 by " + fri(2) + "); point `GcsExtractLanding` at the extract bucket; replace one stub at a time."],
    ["Invoice-ready signal: definition and read access (item B3)", "SAP team; Pricing and Billing", "Candidate in Stage 1; agreed in Stage 2 (by " + fri(5) + ")", "Prototype B1 on the candidate (billing due list or goods-issued deliveries without an invoice); make the definition a configuration value."],
    ["Business rules: variances per check, source-wins rule, portal rules of the Customers in scope, freight and fuel-rate source; UoM and currency rules (item B4)", "Pricing and Billing; Commercial", "Stage 1, confirmed at Gate 1 (" + g1 + ")", "Put them in `prebill_agent/policy.py` configuration and the rate tables; the fixtures carry Ingredion's brief values until then."],
    ["Named owner per outcome and human step; review-queue users and notification channel (item B5)", "Sponsor; use-case lead", "Owners in Stage 1; channel and users by Gate 2", "Fill the owner map in B7; configure the channel (section 10)."],
    ["Root-cause analysis of 6 Aug 2026, solution brief of 7 Oct 2026, dispute volumes by type (item B7)", "Agent B use-case lead", "Week 0", "Baseline B-D1: volumes, dispute types, manual effort; the preventable share estimate."],
    ["Dev GCP project with Vertex AI, Document AI, Model Armor, Cloud Run and quota (item 16)", "GCP platform team", "Week 0", "Run sections 5.1 to 5.4; one Gemini call from the B3 prototype; Document AI processor."],
    ["Dedicated service account, IAM, region (item 17)", "Platform and security", "Week 0", "Bind the roles in 5.2; set Application Default Credentials; run the authorization test skeleton (read-only proof)."],
    ["Connectivity to API Management, PROS, Salesforce, Ariba (item 18)", "Network and security", "Decision week 0; path by " + fri(2), "Request the connector and NAT address; send it for allow-listing; extracts to Cloud Storage need no path at all."],
    ["Repository with pipeline permissions (item 19)", "Technical lead", "Week 0", "Push the code (3.2); enable branch protection; wire the pipeline (section 12)."],
    ["Data classification and AI-use approval covering PO, pricing, invoice and Customer data; approved model list (item 20)", "Security and technical lead", "Week 0", "Set `VERTEX_MODEL`; file the approval under `docs/`; no real PO or price reaches Gemini before this."],
    ["Model Armor template (item 21)", "Security", "Stage 1", "Set `MODEL_ARMOR_TEMPLATE`; measure the block rate on the sample."],
    ["Prototype security review within 5 working days of the request (item 22)", "Security", "Request on " + mon(0) + "; clear by " + fri(1), "Raise it on day one with the read-only architecture sketch."],
    ["Ingredion-side changes for invoice-ready orders and source reads by the Gate 2 dates; non-production sources or extracts with test data (item B8)", "Technical lead; system owners", "Gate 2 dates; Stage 3", "SIT in the Test project depends on them; log each in the RAID log."],
    ["User IDs, VPN, Westchester access, Teams channel (item 25)", "IT and facilities", "Week 0", "Switch `gcloud` and Git to the Ingredion identity."],
  ],
  iamRoles: [
    ["roles/aiplatform.user", "Call the approved Gemini model on Vertex AI (B3, B6)"],
    ["roles/documentai.apiUser", "Process scanned POs with the Document AI processor (B3)"],
    ["roles/modelarmor.user", "Screen text with the Model Armor template before every model call"],
    ["roles/secretmanager.secretAccessor", "Read the secrets mounted into the service (5.3)"],
    ["roles/logging.logWriter, roles/cloudtrace.agent, roles/monitoring.metricWriter", "Structured logs, traces and custom metrics"],
    ["roles/storage.objectViewer on the extract and sample buckets; roles/storage.objectUser on the documents bucket only", "Scheduled extracts are read, never written, by the agent"],
    ["Nothing else", "No Editor, no Owner; the deployer account deploys; no write credential to any source system exists in this project"],
  ],
  secrets: [
    ["ingredion-api-key", "Shared secret for the review and ops API until single sign-on replaces it", "app/auth.py"],
    ["mongo-uri", "Connection string of the shared stores (if MongoDB Atlas is chosen in B-D11)", "factory/settings.py"],
    ["apim-subscription-key, sap-client-id, sap-client-secret", "Azure API Management subscription and OAuth client for the SAP read services (read-only scope)", "connectors/sap_billing.py"],
    ["pros-api-key (if PROS has a read API)", "PROS price record reads; otherwise none, the extract lands in Cloud Storage", "connectors/pros.py"],
    ["salesforce-client-id, salesforce-jwt-key", "Connected app for reading cases and PO documents", "connectors/salesforce_orders.py"],
    ["ariba-api-key (if Ariba's API is used)", "Customer PO reads from Ariba; otherwise an export", "connectors/ariba.py"],
  ],
  buckets: [
    ["ingredion-pb-samples-ENV", "The sample of past invoiced orders with PO, SAP order, delivery and billing data and outcomes (incl. the anchor case)", "Read-only after load; Dev and Test only (approved historical data, SOW 5.2)"],
    ["ingredion-pb-extracts-ENV", "Scheduled extracts for sources without a read interface: PROS, TermSync, contract and fuel-rate files, one prefix per source with a timestamped file (`GcsExtractLanding.latest(source)`)", "Lifecycle rule keeps the last N extracts; written only by Ingredion's export job or a transfer, never by the agent"],
    ["ingredion-pb-documents-ENV", "PO PDFs and portal records read by B3, keyed by order", "Lifecycle rule per the 5.3 policy for source documents; event-based hold for legal hold"],
  ],
  reasonCodes: [
    ["PRICE.PO_STALE, PRICE.SAP_WRONG, PRICE.MISSING_SAP", "REVIEW", "Unit price gap after conversion: PO out of date (SAP right), SAP wrong, or no SAP price"],
    ["FREIGHT.NOT_ON_PO, FREIGHT.SAP_WRONG, FREIGHT.NO_TERMS", "REVIEW", "Freight charged but not on the PO; SAP freight wrong; no terms to compare against"],
    ["SURCHARGE.NOT_ON_PO, SURCHARGE.SAP_WRONG, SURCHARGE.NO_TERMS", "REVIEW", "Fuel surcharge gaps, same pattern"],
    ["QTY.OVER, QTY.UNDER", "REVIEW", "Shipped quantity outside the PO range (over-shipments first)"],
    ["TERMS.PO_STALE, TERMS.SAP_WRONG, TERMS.MISSING", "REVIEW", "Payment terms differ or are missing"],
    ["LINE.UNPAIRED", "REVIEW", "A PO line could not be matched to an SAP line after normalisation"],
    ["PO.NOT_FOUND, DATA.MISSING", "REVIEW", "The Customer PO or another required record could not be retrieved; the missing item is named"],
    ["EXTRACT.FORMAT_ERROR, EXTRACT.LOW_CONFIDENCE, GUARD.BLOCKED", "REVIEW", "B3 could not read the PO with confidence, or the guardrail refused the text"],
    ["KILL_SWITCH", "INFO", "Pick-up stopped by the operator"],
  ],
};

function whatYouBuild() {
  return [
    H1("2. What you are building"),
    P("Agent B adds one step between invoice-ready and invoice-sent: a PO alignment check. For each invoice-ready order it assembles the evidence people search for by hand today (SAP, PROS, Salesforce, Ariba, TermSync, the contract and fuel-rate files), reads the Customer PO, compares price, freight and surcharge, quantity and payment terms with the PO, explains each gap and drafts the PO-update request for the named Ingredion owner (SOW 3.1). The agent is read-only: it changes nothing in SAP or PROS, releases no invoice and contacts no Customer. In production an Ingredion owner decides and acts on every flagged case."),
    H2("2.1 The eight steps and where each one lives"),
    T(["Step (SOW 3.3)", "What happens", "Runs on", "Reads and writes", "Exit", "Module"], [
      ["B1 Pick up the invoice-ready order", "Identifies the orders that are ready to invoice (definition agreed in Stage 2, approved at Gate 2)", "Code", "SAP (read)", "None", "`steps/b1_pickup.py`"],
      ["B2 Assemble the evidence", "Order, delivery and billing data, the price record, the Customer PO, contract and fuel-rate records, dispute history", "Code", "SAP, PROS, Salesforce, Ariba, TermSync, rate files (read)", "Missing data: flagged with the item named, to the owner", "`steps/b2_evidence.py`"],
      ["B3 Read the PO", "Price, unit, quantity and range, charges and payment terms from the PO with a confidence per field; guardrails first", "Gemini and Document AI", "None", "None; one re-read on a field error", "`steps/b3_read_po.py`, prompt `b3_read_po.v1`"],
      ["B4 Normalise and match lines", "Units (CWT, lb, kg) and currency converted; each PO line matched to its SAP line", "Code", "None", "A line cannot be matched: missing data", "`steps/b4_normalise.py`, `normalise.py`"],
      ["B5 Compare", "The four checks against the agreed variances; one of three outcomes", "Code (rules)", "None", "Matched: recorded, no further action", "`steps/b5_compare.py`, `rules.py`"],
      ["B6 Explain and draft", "Plain-language explanation of each gap with its evidence; the PO-update request drafted", "Gemini", "None", "None", "`steps/b6_explain.py`, prompt `b6_explain.v1`"],
      ["B7 Route", "The case goes to the named owner for its outcome through the review queue and the notification channel", "Code", "Review queue (own), notification channel", "Human judgment gate", "`steps/b7_route.py`, `factory/review/`"],
      ["B8 Record", "The owner's decision, reason and evidence; the case closes when the owner marks it aligned; a recheck runs when an updated PO arrives", "Code", "Audit trail (own)", "None", "`steps/b8_record.py`"],
    ], [2, 4, 1.3, 2.6, 2.4, 2.6]),
    H2("2.2 Four checks, three outcomes, who acts (SOW 3.3, 3.5)"),
    T(["Check", "Rule in the first release", "Module"], [
      ["Price", "Must match exactly after unit-of-measure and currency conversion", "`UnitPriceRule`"],
      ["Freight and surcharge", "Any charge that is not on the PO is flagged", "`FreightRule`, `FuelSurchargeRule`"],
      ["Quantity", "Must fall within the PO range; over-shipments come first", "`QuantityRule`"],
      ["Payment terms", "Must match exactly", "`PaymentTermsRule`"],
    ], [2, 5, 3]),
    T(["Outcome", "Meaning", "Who acts"], [
      ["Matched", "The invoice agrees with the PO within the agreed variances", "Nobody; the result is recorded"],
      ["Updated PO required", "SAP is right and the PO is out of date", "Customer Service or Commercial requests the updated PO from the Customer, using the agent's draft"],
      ["Fix our side or decide", "SAP is wrong, or it is unclear which source is right", "Ingredion corrects its own side (price changes sit with CBA, Sales and PROS), or a person decides"],
    ], [2, 4, 4]),
    P("Which source wins: SAP is what Ingredion bills, the PO is what the portal checks; if SAP is right the Customer updates the PO, if SAP is wrong Ingredion fixes its side, if unclear a person decides. The variances are Ingredion's; the first release uses the ones in the brief and they are confirmed at Gate 1 and fixed in B-D8 at Gate 2. **Out of scope (SOW 10):** the order-entry check, fixing orders that ship without a price, any change to SAP or PROS, holding or releasing invoices, contacting Customers, anything after the invoice is sent, dispute types beyond the four checks, orders outside the United States and Canada."),
    H2("2.3 The anchor case and the scorecard (SOW 3.2, 3.4)"),
    P("Kraft Heinz sales order 809-6862 is the anchor test case and the first release must catch all four of its gaps: price USD 40.14 per CWT on the PO against 47.00 on the invoice (July price used for an August shipment); a USD 300 fuel surcharge added at shipment and not on the PO; 170,250 lb shipped against 170,000 lb ordered (Ariba hard-blocks the over-quantity); 110 days on the invoice against 120 on the PO (PROS had no Net 110 option). `prebill_agent/fixtures.py` carries this world and `python -m factory.evaluation prebill` must return 4 of 4 with no false alarms on every build."),
    T(["Measure", "Proposed threshold (starting point; confirmed at Gate 1 from the backtest)"], [
      ["Catch rate", "At least 95% of real gaps caught, including all four gaps in the anchor case"],
      ["False alarms", "No more than 10% of flagged cases"],
      ["Traceability", "100% of results traceable to their evidence"],
      ["Reviewer agreement", "At least 85% of outcomes confirmed by the reviewer"],
      ["Time saved", "At least 30% against the Stage 1 baseline"],
      ["Actions without a person", "Zero"],
      ["Missing data", "100% of missing-data cases flagged, and no more than 15% of cases"],
    ], [3, 7]),
    P("Size of the problem (SOW 3.2): Ingredion's root-cause analysis of 6 August 2026 counts 26,860 open or late invoices in the United States and Canada, 3,155 coded Pricing Discrepancy and 674 Freight Bill Disputed. The share a pre-bill check can prevent is measured in Stage 1; the SOW assumes no figure."),
  ];
}

function timeline() {
  const stages = [
    ["Week 0 Mobilisation", "0", mon(0) + " to " + fri(0), "none", "Access and the sample in place; the sample size agreed"],
    ["Stage 1 Discovery and Assessment", "1 to 3", mon(1) + " to " + fri(3), "Gate 1, " + g1, "Sponsor: go/no-go for build; validation location decided; variances, thresholds and plan confirmed"],
    ["Stage 2 Solution Design", "4 to 5", mon(4) + " to " + fri(5), "Gate 2, " + g2, "Technical lead: design approval; invoice-ready definition agreed; architecture and security review complete"],
    ["Stage 3 Build", "6 to 9", mon(6) + " to " + fri(9), "Gate 3, " + g3 + " (New Year's Day; hold the review on 30 or 31 December)", "Ready for test: requirements built, evaluation passing in Dev, documentation and test cases delivered"],
    ["Stage 4 Test and Validation", "10 to 12", mon(10) + " to " + fri(12), "Gate 4, " + g4, "Release approval: UAT signed off, thresholds met, no open critical or high findings, run model agreed, production change approved"],
    ["Stage 5 Production Release", "13 to 15", mon(13) + " to " + fri(15), "Gate 5, " + g5, "Sponsor: production acceptance; decision on later dispute types"],
    ["Stage 6 Hyper Care and Handover", "16 to 19", mon(16) + " to " + fri(19), "Gate 6, " + g6 + " (week 20)", "Run owner accepts; Ingredion and the AMS partner sign off the Knowledge Transition"],
  ];
  const comps = [
    { band: "Week 0 and Stage 1" },
    ["Local environment, repository move, pre-existing materials note; sample size agreed", "none", "0", by(0), "Repository (item 19)"],
    ["Dev project configured, one Gemini call, Document AI processor", "B-D3 prep", "0 to 1", by(1), "Items 16, 17, 20"],
    ["Baseline and dispute classification (walkthrough, root-cause analysis validated, volumes by type, manual effort)", "B-D1", "1 to 2", by(2), "Items B6, B7"],
    ["Source systems: read interface or extract per source, candidate invoice-ready signal, freight data completeness", "B-D3 (sources)", "1 to 2", by(2), "Items B2, B3"],
    ["Prototype in Dev: B2 to B6 on the sample", "B-D5 (prototype)", "1 to 2", by(2), "Sample, data approval, Model Armor"],
    ["Interim review", "B-D4", "2", "week of " + mon(2), "Steering attendance"],
    ["Test-case set and gap map (which source wins per gap type)", "B-D2", "1 to 3", by(3), "Reference outcomes confirmed by " + fri(2)],
    ["Target architecture incl. validation-location recommendation", "B-D3", "1 to 3", by(3), "Items 16 to 18"],
    ["Backtest report against the scorecard, by check, Customer and gap type; proposed variances and thresholds", "B-D5 (report)", "2 to 3", by(3), "Anchor case 4 of 4"],
    ["Business case (preventable share, value, run cost) and pilot plan; executive readout", "B-D6, B-D7", "2 to 3", by(3), "Item B7 volumes"],
    { band: "Stage 2" },
    ["Requirements, comparison rules and variances for the four checks, routing rules and owners, acceptance criteria", "B-D8", "4 to 5", by(5), "Gate 1 variances"],
    ["Solution design (evidence assembly, PO reading, conversion and matching, rules, outcomes, explanation and draft, review queue and routing, audit, retention)", "B-D9", "4 to 5", "submit by " + mon(5) + " so the 5-day review ends by " + fri(5), "Item 23 (retention)"],
    ["Integration specification (read interfaces, invoice-ready signal, review queue and notification channel)", "B-D10", "4 to 5", "submit by " + mon(5), "Invoice-ready signal agreed; third parties"],
    ["Environment and deployment design; test and evaluation plan", "B-D11, B-D12", "4 to 5", by(5), "Item 26"],
    { band: "Stage 3" },
    ["Dev environment completed and pipelines", "B-D13", "6 to 7", by(7), "Repository, deployer account"],
    ["Agent part 1: B1 to B3", "B-D14", "6 to 7", by(7), ""],
    ["Read connectors for SAP, PROS, Salesforce, Ariba, TermSync; landing for files and extracts", "B-D15", "6 to 9", by(9), "Items B2, B8"],
    ["Evaluation suite on every build", "B-D16", "6 to 9", by(9), ""],
    ["Agent part 2: B4 to B5", "B-D14", "7 to 8", by(8), "Christmas week capacity"],
    ["Review queue and notification channel for the owners", "B-D15", "7 to 9", by(9), "Item B5"],
    ["Agent part 3: B6 to B8; retention rules", "B-D14", "8 to 9", by(9), "New Year capacity"],
    ["Dashboards and alerts; build documentation, baseline and developer test cases", "B-D16, B-D16a/b/c", "8 to 9", by(9), ""],
    { band: "Stage 4" },
    ["Test environment connected to non-production sources or extracts", "B-D17", "10", by(10), "Test project (Stage 3)"],
    ["SIT and evaluation on unseen past orders", "B-D18", "10 to 12", by(12), ""],
    ["Security testing per 5.4 (incl. proof the agent cannot write) and report; performance test; UAT support", "B-D19", "10 to 12", by(12), "UAT users nominated"],
    ["Release notes, go-live checklist, rollback rehearsal, run model", "B-D20", "11 to 12", by(12), "Item 27"],
    { band: "Stage 5 and 6" },
    ["Production deployment (read-only access)", "B-D21", "13", by(13), "Prod project, change ticket"],
    ["Shadow mode run and report (one week)", "B-D22", "13", by(13), ""],
    ["Owner onboarding; assisted mode run and report", "B-D23", "13 to 15", by(15), "Owners available"],
    ["Hyper care weekly reports", "B-D24", "16 to 19", by(19), ""],
    ["Runbook, owner guide, KT sessions, reverse shadowing, KT sign-off", "B-D25", "14 to 19", by(19), "AMS partner available"],
    ["Closure report", "B-D26", "19 to 20", by(20), ""],
  ];
  return [
    H1("4. Timeline and deadlines"),
    P("Agent B starts in the same Week 0 as Agent A and runs 16 weeks including Week 0 to production acceptance at Gate 5, then four weeks of hyper care and closure at Gate 6 in week 20 (SOW 1.3, 7.0). Its plan is one week shorter than Agent A's in Build and in Production Release because the agent only reads and creates nothing in SAP. This plan supersedes the 10-week proof-of-concept calendar in Ingredion's solution brief of 7 October 2026."),
    H2("4.1 Stages and gates"),
    T(["Stage", "Weeks", "Dates", "Gate", "Decided by and criteria (SOW 4.2)"], stages, [2.3, 1, 2.6, 2.2, 3.4]),
    H2("4.2 Component deadlines (from the WBS of 23 October 2026)"),
    P("The build window is the WBS's planned span; \"done by\" is the Friday of its last week. A component that depends on an Ingredion input inherits that input's lateness day for day."),
    T(["Component", "Deliverable", "Weeks", "Done by", "Depends on"], comps, [4, 1.6, 1, 2.2, 2.4]),
    H2("4.3 Calendar risks already visible"),
    UL([
      "**Diwali, Friday 6 November (week 1):** a non-working day for the Pune team in the first prototype week.",
      "**Thanksgiving, 26 and 27 November (week 4):** two of Stage 2's ten working days without Ingredion, in the stage that must agree the invoice-ready definition and the variances. Submit B-D9 and B-D10 by Monday " + mon(5) + ".",
      "**Christmas and New Year (weeks 8 and 9):** the second half of Stage 3, with Gate 3 falling on " + g3 + ". Hold the gate review on 30 or 31 December and have B-D16a/b/c written during the build.",
      "**One shadow week (week 13):** the comparison harness and the owner onboarding material must be ready before Gate 4 (" + g4 + "), or the week is spent building them.",
      "**Every Ingredion period is 5 working days.** Raise each request early in the week and log it in the RAID log the same day.",
    ]),
  ];
}

function stepBlock(title, rows) { return [H2(title), T(["", ""], rows, [1.6, 8.4])]; }
function steps() {
  const p1 = by(7), p2 = by(8), p3 = by(9), proto = by(2);
  return [
    H1("8. Build the steps B1 to B8"),
    P("The step contract is the same as Agent A's: `run(case, ctx) -> StepResult`, typed data in `case.data`, flags only through reason codes, dispositions CONTINUE, RETRY, REVIEW, EXIT or DONE. `prebill_agent/pipeline.py` owns the order (B1 to B8), parking at B7, `resume(case, decision)` after the owner decides and `recheck(case, updated_po)` when an updated PO arrives, which re-runs from B2. Rules decide, AI explains, people act (SOW 1.6)."),
    P("Build order: the Stage 1 prototype runs B2 to B6 on the sample (" + proto + "); Stage 3 then builds B1 to B3 (" + p1 + "), B4 to B5 (" + p2 + ") and B6 to B8 (" + p3 + ") as the WBS splits B-D14."),
    CODE(`# The rule engine is ordinary code (prebill_agent/rules.py, shortened)
class UnitPriceRule(Rule):
    code = "unit_price"
    def check(self, mc: MatchContext) -> RuleResult:
        po, sap = mc.po_price_per_unit, mc.sap_price_per_unit      # both after UOM and currency conversion (B4)
        if po is None or sap is None:
            return self.result(False, "PRICE.MISSING_SAP", Verdict.MISSING_DATA, evidence=mc.evidence("price"))
        if _close(po, sap, mc.policy.price_tolerance):
            return self.result(True, None, Verdict.MATCHED)
        verdict = Verdict.UPDATED_PO_REQUIRED if mc.sap_price_is_current else Verdict.INTERNAL_FIX
        return self.result(False, "PRICE.PO_STALE" if verdict is Verdict.UPDATED_PO_REQUIRED else "PRICE.SAP_WRONG", verdict, evidence=mc.evidence("price"))

ruleset = build_ruleset(policy.checks)              # the four checks of the first release
results = ruleset.run(mc); outcome = overall_outcome(results); who = owners(results)`),
    ...stepBlock("B1 Pick up the invoice-ready order (`steps/b1_pickup.py`)", [
      ["Purpose", "Find the orders whose invoice is ready but not sent, exactly once each (SOW 3.3 B1; Appendix 1 \"invoice-ready\")."],
      ["Today", "`SAPBilling.list_ready(after)` returns `DraftInvoiceRef`s from the stub; the pipeline claims each (one-case-once) and checks the kill switch."],
      ["Build", "1. The invoice-ready signal is defined in Stage 2 and approved at Gate 2 (" + g2 + "); prototype on the candidate confirmed in Stage 1 (for example the billing due list, or deliveries with goods issue and no billing document) and keep the definition in configuration. 2. A watermark per run persisted in the case store; a scheduler call every few minutes (5.4). 3. Only United States and Canada orders (SOW 10.1)."],
      ["Codes", "KILL_SWITCH."],
      ["Tests", "`StubSAPBilling` lists; add an order that disappears between list and read."],
      ["Done by", p1],
    ]),
    ...stepBlock("B2 Assemble the evidence (`steps/b2_evidence.py`)", [
      ["Purpose", "Collect what people search for by hand: order, delivery and billing data, the price record, the Customer PO, the contract and fuel-rate records, the dispute history (SOW 3.3 B2)."],
      ["Today", "Reads through `SAPBilling.draft_invoice`, `shipment`, `price_condition`, `payment_terms`; `PROS.contract_price`, `contract_terms`; `SalesforceOrders.order`; `Ariba.purchase_order`; `TermSync.dispute_history`; `RateFiles.freight_terms`, `surcharge_terms`, `material_factors`; `Mailbox.find_po_pdf`. A missing record flags DATA.MISSING with the item named and the case goes to the owner; the agent never guesses."],
      ["Build", "1. Six real clients or extract loaders (section 9) behind the same protocols. 2. Record the source and timestamp of every piece of evidence on the case; traceability must be 100% (3.4). 3. Freight data completeness in SAP is a Stage 1 finding (B-D3); design for the case where freight comes only from the rate files."],
      ["Codes", "DATA.MISSING, PO.NOT_FOUND."],
      ["Tests", "Fixture worlds (`kraft_heinz_world`, `clean_world`, `converted_units_world`, `missing_po_world`); add a world with freight only in the rate files."],
      ["Done by", "Prototype " + proto + "; step " + p1 + "; connectors " + p3],
    ]),
    ...stepBlock("B3 Read the PO (`steps/b3_read_po.py`, prompt `b3_read_po.v1.md`)", [
      ["Purpose", "Extract price, unit, quantity and range, charges and payment terms from the Customer PO with a confidence per field (SOW 3.3 B3)."],
      ["Today", "Structured extraction into the `CanonicalDoc` schema shared with the SAP side; one re-read on a field error; guardrails before the call; prompts versioned."],
      ["Build", "1. Multimodal route for PDF POs (6.3) and Document AI for scans (section 7), decided on the sample. 2. Portal records (Ariba) arrive structured and skip the model; keep that path cheap. 3. Tolerance phrases on POs (\"plus or minus 10%\") are read into the quantity range; a PO with no printed tolerance means exact (`qty_default_tolerance_pct`)."],
      ["Codes", "EXTRACT.FORMAT_ERROR, EXTRACT.LOW_CONFIDENCE, GUARD.BLOCKED."],
      ["Tests", "The anchor PO as a golden file once Ingredion approves it for tests; a scanned PO; an Ariba record."],
      ["Done by", "Prototype " + proto + "; final " + p1],
    ]),
    ...stepBlock("B4 Normalise and match lines (`steps/b4_normalise.py`, `prebill_agent/normalise.py`)", [
      ["Purpose", "Convert units (CWT, lb, kg) and currency and match each PO line to its SAP line before anything is compared (SOW 3.3 B4)."],
      ["Today", "`MASS_TO_LB`, `qty_factor`, `convert_qty`, `convert_price`, `StaticRates` for currency, `pair_lines` by material and quantity; `UnitError` and LINE.UNPAIRED for the rest."],
      ["Build", "1. Material factors from SAP (`RateFiles.material_factors` or the material master): bag weights and pallet factors are data, never constants in code. 2. Currency rates from Ingredion's source with the rate date recorded. 3. Pairing rules confirmed on the sample (material number first, then Customer material, then description)."],
      ["Codes", "LINE.UNPAIRED."],
      ["Tests", "`converted_units_world`; add a kg PO against a CWT invoice and a multi-line PO with one unmatched line."],
      ["Done by", p2],
    ]),
    ...stepBlock("B5 Compare (`steps/b5_compare.py`, `prebill_agent/rules.py`)", [
      ["Purpose", "Apply the four checks against the agreed variances and give the order one of three outcomes (SOW 3.3 B5)."],
      ["Today", "`build_ruleset(policy.checks)` with `UnitPriceRule`, `FreightRule`, `FuelSurchargeRule`, `QuantityRule`, `PaymentTermsRule`; `overall_outcome` (Matched, Updated PO required, Fix our side or decide, including missing data); `owners` per rule; `RELEASE_CHECKS = {1: ALL_CHECKS}`."],
      ["Build", "1. Ingredion's variances and the source-wins rule as configuration confirmed at Gate 1 (" + g1 + ") and fixed in B-D8 at Gate 2; a change afterwards is release-approved like a prompt change. 2. Portal rules of the Customers in scope (for example Ariba hard-blocks over-quantity) as rule parameters per Customer. 3. Every result carries its evidence references; the Matched outcome is recorded with them too."],
      ["Codes", "PRICE.*, FREIGHT.*, SURCHARGE.*, QTY.OVER, QTY.UNDER, TERMS.*."],
      ["Tests", "The anchor must produce exactly four failures and the clean world none; add one case per variance boundary."],
      ["Done by", p2],
    ]),
    ...stepBlock("B6 Explain and draft (`steps/b6_explain.py`, prompt `b6_explain.v1.md`)", [
      ["Purpose", "Say in plain language what differs, by how much and which records show it; draft the PO-update request where the outcome is Updated PO required (SOW 3.3 B6)."],
      ["Today", "Gemini writes the explanation and the draft from the rule results and evidence; a template is the fallback, never silence; the draft is for the owner to send."],
      ["Build", "1. Screen the explanation and the draft with Model Armor's response filter before they reach the queue. 2. Internal note instead of a Customer draft for Fix our side or decide. 3. Tune the prompt on the backtest explanations the owners rate as clear (reviewer agreement is a scorecard measure)."],
      ["Codes", "GUARD.BLOCKED."],
      ["Tests", "`B6_ANSWER` fixture; add a missing-data case where the explanation must name the missing record."],
      ["Done by", p3],
    ]),
    ...stepBlock("B7 Route (`steps/b7_route.py`, `factory/review/`)", [
      ["Purpose", "Send every case that is not Matched to the named owner for its outcome, with the explanation and the evidence side by side (SOW 3.3 B7 and the human judgment gate)."],
      ["Today", "A `ReviewItem` per flagged invoice addressed to the owner the redline names (Customer Service or Commercial; Ingredion owner incl. CBA, Sales, PROS); the issue owner per rule is recorded; the REST router serves the queue; decisions resume the pipeline."],
      ["Build", "1. The owner map from Ingredion's names (item B5, confirmed in Stage 1). 2. The notification channel confirmed in Stage 2 (section 10). 3. Whether an invoice is held while a case is open is an Ingredion process decision; the agent does not hold or release invoices (SOW 3.3)."],
      ["Codes", "None of its own; the case carries the rule codes."],
      ["Tests", "`test_prebill_pipeline.py` routing and owner assertions; add an outcome with two issue owners."],
      ["Done by", p3],
    ]),
    ...stepBlock("B8 Record (`steps/b8_record.py`, `factory/audit/`)", [
      ["Purpose", "Record the owner's decision, the reason and the evidence; close the case when the owner marks it aligned; re-run from B2 when an updated PO arrives (SOW 3.3 B8)."],
      ["Today", "Append-only audit record per order; `pipeline.recheck(case, updated_po)` runs B2 to B8 again and keeps both results."],
      ["Build", "1. The recheck trigger: a new PO on the Salesforce case or in Ariba, detected by B1's next pass or by the owner from the queue. 2. Retention per record category (section 11). 3. Export of the per-order record for the scorecard reporting (3.4) and for Ingredion's later SIEM (10.3)."],
      ["Codes", "None."],
      ["Tests", "Recheck path in the pipeline tests; a decision after the case closed must be refused (409)."],
      ["Done by", p3],
    ]),
  ];
}

function connectors() {
  return [
    H1("9. Connectors (B-D15): six sources, all read-only"),
    P("Every connector implements a protocol in `prebill_agent/connectors/__init__.py` and is constructed in `prebill_agent/runtime.py` from settings. Where a system has no read interface, Ingredion provides a scheduled data extract (SOW 8.1(b)); it lands in the extract bucket and `GcsExtractLanding.latest(source)` in `connectors/extracts.py` finds the newest file per source. The decision per source is a Stage 1 finding (B-D3 by " + friD(2) + ") and the integration specification is B-D10 (" + friD(5) + "). All connectors done by " + friD(9) + "."),
    T(["Source", "Protocol", "Read interface candidate", "Extract alternative", "Notes"], [
      ["SAP: order, delivery, billing, pricing, freight; the invoice-ready signal", "`SAPBilling`", "Sales order, outbound delivery, billing document and condition record read services behind Azure API Management (same APIM and credential pattern as Agent A, read-only scope)", "Daily extract of invoice-ready orders with their documents", "The invoice-ready definition is agreed in Stage 2; freight completeness is a Stage 1 finding"],
      ["PROS: price records and contract terms", "`PROS`", "PROS REST API for price agreements, if licensed for integration", "Scheduled export of active price agreements to Cloud Storage", "The anchor case's Net 110 gap lives here"],
      ["Salesforce: the case, the order reference and the PO document", "`SalesforceOrders`, `Mailbox`", "Connected app with JWT bearer flow, read-only permission set on Case, EmailMessage, ContentVersion", "Not needed; the API is standard", "The PO PDF is usually the email attachment on the original case"],
      ["Ariba: Customer POs held in the portal", "`Ariba`", "Ariba supplier APIs or cXML order retrieval where Ingredion has supplier access", "Periodic export of open POs", "Portal rules (hard blocks) come from here too"],
      ["TermSync: dispute and payment records", "`TermSync`", "Reporting API if available", "Scheduled export of disputes and payment status", "Used for dispute history and for the shadow-mode comparison"],
      ["Contract and fuel-rate files", "`RateFiles`", "None; these are files (Excel) maintained by Ingredion", "The files copied to the extract bucket on a schedule (SharePoint to Cloud Storage transfer)", "Version every file; record which version each case used"],
    ], [2.2, 1.3, 3, 2.3, 2.2]),
    UL([
      "**Authentication:** APIM subscription key and OAuth client credentials for SAP (read-only scope), API keys or OAuth clients for PROS and Ariba where APIs exist, the JWT bearer certificate for Salesforce; all in Secret Manager. The runtime service account itself has no write role anywhere.",
      "**Extract landing:** one prefix per source in `ingredion-pb-extracts-ENV`, files named with a timestamp, a manifest with row counts; the loader validates the schema and refuses a file that is older than the agreed freshness. The agent only reads the bucket; Ingredion's export job or a transfer writes it.",
      "**Tests:** recorded responses per source replayed in tests; the stubs in `connectors/stubs.py` stay for the pipeline tests.",
    ]),
  ];
}

function reviewScreen() {
  return [
    H1("10. The human gate: owner queue and notification channel"),
    P("Every case that is not Matched goes to a named Ingredion owner through a review queue (SOW 3.3 B7). The queue is the shared factory component (`/api/review/items`, `/api/review/items/{id}`, `/api/review/items/{id}/decision`); the notification channel is confirmed in Stage 2 (B-D10) and the owners and queue users are provided by Ingredion (item B5)."),
    H2("10.1 What exists"),
    UL([
      "The review router and queue shared with Agent A; `ReviewItem`s addressed to the owner per outcome with the rule results, evidence references, the explanation and the drafted PO-update request or internal note.",
      "Decisions: confirm the outcome, override it (with the owner's reason), or mark the case aligned after acting; `resume` records the decision through B8; a recheck can be requested when the updated PO arrives.",
      "Identity today is an API key plus `X-User-Id`: a stand-in for Dev only.",
    ]),
    H2("10.2 What to build (usable by Gate 3, " + g3 + "; hardened for UAT by " + friD(10) + ")"),
    OL([
      "**The owner screen:** the same small web application pattern as Agent A on Cloud Run behind Identity-Aware Proxy with Ingredion's identity provider; the queue filtered by owner and outcome; one case with PO values and SAP values side by side per check, the evidence references as links, the explanation, and the draft with a copy button or an \"open in Outlook\" link. Confirm, override and \"aligned\" buttons; a comment field for the reason.",
      "**The notification channel (Stage 2 decision):** email to the owner from a shared mailbox through Microsoft Graph (Mail.Send scoped to that one mailbox, a different scope from Agent A's draft-only permission), a Teams channel post through an incoming webhook, or a Salesforce task on the case. The notification carries a link to the queue item, never the data itself.",
      "**Owner guide:** draft for onboarding in week 13 (B-D23), final in B-D25.",
    ]),
  ];
}

function testing() {
  return [
    H1("13. Testing, evaluation and the Stage 1 backtest"),
    H2("13.1 Unit tests and the fixtures"),
    UL([
      "`prebill_agent/fixtures.py` builds complete worlds: `kraft_heinz_world()` (the anchor), `clean_world()`, `converted_units_world()`, `missing_po_world()`; `build(world, b6_answers=[B6_ANSWER])` returns a harness with the pipeline. Every new rule parameter or connector behaviour gets a world and a pipeline test in `tests/prebill/test_prebill_pipeline.py`.",
      "`python -m factory.evaluation prebill` runs the anchor and the other worlds through the pipeline and must report `anchor_caught: 4/4` and `false_alarm_rate: 0.0`; it is the Gate 3 \"evaluation passing in Dev\" in miniature and runs on every build.",
    ]),
    H2("13.2 The evaluation suite (B-D16)"),
    P("`factory/evaluation/prebill.py` scores `PrebillCase`s (expected flags against predicted flags, traceability, reviewer agreement, unattended actions) into the scorecard of SOW 3.4 with its verdict bands. Make the Stage 1 test-case set (B-D2) the fixed evaluation set in the Dev bucket; run it with the fake model in CI and with the real model nightly in Dev; a drop in catch rate or a rise in false alarms against the released version blocks the release."),
    H2("13.3 The Stage 1 backtest, step by step (B-D5 report by " + friD(3) + ")"),
    OL([
      "**Receive the sample (by 2 November 2026, item B1):** past invoiced orders in the number agreed in Week 0, representing the mix of gaps, each with the Customer PO, the SAP order, delivery and billing data and the dispute or payment outcome; the anchor case among them. Load into `ingredion-pb-samples-dev`, one folder per order with a manifest.",
      "**Build the test-case set (B-D2):** for each order the expected outcome and the expected gaps per check, confirmed by Ingredion (by " + friD(2) + ", 8.1(c)); classify the gap types and which source wins for each.",
      "**Run the prototype (by " + friD(2) + "):** B2 to B6 in Dev with the real model, Model Armor on, Document AI for scanned POs; store every extraction and rule result for re-scoring.",
      "**Score against the scorecard:** catch rate per check, per Customer and per gap type; false alarms; missing-data share; traceability; tokens, pages and latency per order for the run-cost estimate. The anchor must be 4 of 4.",
      "**Propose variances and thresholds:** where the brief's exact-match rules produce false alarms, show the distribution and propose the variance for Ingredion to confirm at Gate 1 (" + g1 + "); propose the Gate 4 and Gate 5 thresholds.",
      "**Write B-D5** with the method, the numbers, the preventable share estimate for B-D6 and the recommendation on validation location; present at the executive readout in the week of " + mon(3) + ".",
    ]),
    H2("13.4 Stage 4: SIT, unseen-order evaluation, UAT, performance (" + mon(10) + " to " + fri(12) + ")"),
    UL([
      "SIT in the Test project against non-production source systems or the agreed extracts (B-D17 by " + friD(10) + "): end to end from an invoice-ready order to a routed case and a recorded decision (B-D18 by " + friD(12) + ").",
      "Evaluation on past orders not used during build, per check against the Gate 1 thresholds (B-D18).",
      "UAT by the owners from the week of " + mon(11) + "; sign-off within 5 working days of completion (8.1(e)).",
      "Performance test in the week of " + mon(11) + " at expected volumes: Ingredion's analysis counts 26,860 open or late invoices in a period; size the daily invoice-ready volume with the SAP team in Stage 1 and test at that rate with headroom.",
      "Security testing and the 5.4 report (B-D19), including the proof that the agent cannot write to any source system, the rollback rehearsal and the run model (B-D20) complete the Gate 4 pack (" + g4 + ").",
    ]),
  ];
}

function deliverables() {
  const rows = [
    { band: "Stage 1 (weeks 1 to 3; Gate 1 " + g1 + ")" },
    ["B-D1", "Baseline and dispute classification", by(2)], ["B-D2", "Test-case set and gap map", by(3)], ["B-D3", "Target architecture (read interface per source, security, audit, monitoring; validation-location recommendation)", by(3)], ["B-D4", "Interim review session", "week of " + mon(2)],
    ["B-D5", "Prototype and backtest report with proposed variances and thresholds", "prototype " + by(2) + "; report " + by(3)], ["B-D6", "Business case (preventable share, value, run cost) and pilot plan", by(3)], ["B-D7", "Executive readout", "week of " + mon(3)],
    { band: "Stage 2 (weeks 4 to 5; Gate 2 " + g2 + ")" },
    ["B-D8", "Requirements, comparison rules and variances, routing rules and owners, acceptance criteria", by(5)], ["B-D9", "Solution design document", "submit " + mon(5)], ["B-D10", "Integration specification (read interfaces, invoice-ready signal, review queue, notification channel)", "submit " + mon(5)], ["B-D11", "Environment and deployment design", by(5)], ["B-D12", "Test and evaluation plan", by(5)],
    { band: "Stage 3 (weeks 6 to 9; Gate 3 " + g3 + ")" },
    ["B-D13", "Dev environment completion and pipelines", by(7)], ["B-D14", "Agent (B1 to B3 " + by(7) + "; B4 to B5 " + by(8) + "; B6 to B8 " + by(9) + ")", by(9)], ["B-D15", "Integration components: read connectors, extract landing, review queue and notification channel", by(9)],
    ["B-D16", "Evaluation suite, build test report, monitoring dashboards and alerts", by(9)], ["B-D16a", "Technical build documentation incl. third-party and open-source list", by(9)], ["B-D16b", "Baseline test cases Ingredion can expand for SIT and UAT", by(9)], ["B-D16c", "Developer test cases with results", by(9)],
    { band: "Stage 4 (weeks 10 to 12; Gate 4 " + g4 + ")" },
    ["B-D17", "Test environment connected to non-production sources or extracts", by(10)], ["B-D18", "SIT and evaluation report (unseen past orders)", by(12)], ["B-D19", "UAT, performance and security report (5.4 findings closed; read-only proven)", by(12)], ["B-D20", "Release readiness pack: release notes, deployment and rollback plan (rehearsed), open defects, go-live checklist, run model", by(12)],
    { band: "Stage 5 (weeks 13 to 15; Gate 5 " + g5 + ")" },
    ["B-D21", "Production deployment (read-only)", by(13)], ["B-D22", "Shadow mode report", by(13)], ["B-D23", "Assisted mode report (incl. owner onboarding)", by(15)],
    { band: "Stage 6 (weeks 16 to 19; Gate 6 " + g6 + ")" },
    ["B-D24", "Hyper care report (weekly)", by(19)], ["B-D25", "Runbook, owner guide, knowledge transfer, Knowledge Transition plan and sign-off record", by(19)], ["B-D26", "Closure report", by(20)],
  ];
  return [
    H1("15. Deliverables checklist with dates"),
    P("Each deliverable is submitted with a short cover note; Ingredion reviews within 5 working days and silence is acceptance (SOW 4.2, 9.0). Keep every deliverable in the repository under `docs/deliverables/`."),
    T(["ID", "Deliverable (SOW 3.7)", "Done by"], rows, [1, 6, 3]),
  ];
}

module.exports = { agent, whatYouBuild, timeline, steps, connectors, reviewScreen, testing, deliverables };
