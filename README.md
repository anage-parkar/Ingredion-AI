# Ingredion — Agentic AI Factory

Code for the two agents Parkar is building for Ingredion under SOW No. 07 (redline v2,
20 October 2026), on one shared runtime, in Ingredion's Google Cloud project:

| | Agent A · Email Order Intake Agent | Agent B · Pre-bill Validation and Dispute Prevention Agent |
|---|---|---|
| Role | Primary processor for every email-order case Salesforce routes to it, cohort by cohort; the Existing RPA keeps unmoved cohorts and stays as fallback until Ingredion retires it | Checks the draft invoice against the PO between invoice-ready and invoice-sent |
| Steps | A1 to A10 (`order_intake_agent/steps/`) | B1 to B8 (`prebill_agent/steps/`) |
| Generative AI (Gemini on Vertex AI, behind Model Armor) | A2 classify, A3 extract (with Document AI for PDFs and scans), A6 draft the customer clarification | B3 read a PDF PO (fallback), B6 explain and draft |
| Reads | gold tables (`gold_cases`, `gold_sales`, `gold_pricing`) and the files bucket | gold tables (`gold_billing`, `gold_sales`, `gold_pricing`, `gold_procurement`, `gold_ar`), the files bucket, the extract landing |
| Writes to Ingredion systems | SAP order (A9) and Salesforce case (A10) **after a reviewer approves**; an Outlook draft via Microsoft Graph (A6) that only the reviewer sends | **None** |
| Writes of its own | evidence bucket, `agent_a_outcomes` | evidence bucket, `agent_b_outcomes` |
| Human gate | every case in Phase 1; Phase 2 is an Ingredion decision at Gate 5 | every case that is not Matched |
| Exits | manual queue (Customer Service), reason on the original case | none; recheck when the updated PO arrives |

This repository (`anage-parkar/Ingredion-AI`) is Parkar's development workspace for
the engagement. At engagement start the code moves to Ingredion's Git platform and
runs on Cloud Run in the Ingredion Google Cloud project; nothing here assumes
otherwise, and nothing here talks to any provider but Google Cloud, Salesforce, SAP
(through API Management) and Microsoft Graph. The agent workflows, the data architecture and the document
index are in `Ingredion_docs/` (`ingredion-agent-workflows.html`,
`ingredion-data-architecture.html`, `README.md`).

## Layout

```
Ingredion/
├── factory/                       shared runtime, imported by both agents, imports neither
│   ├── case.py                    Case, Flag, StepResult (the unit of work)
│   ├── intake/                    state machines (A and B), one-case-once claims, pollers
│   ├── guardrails/                PatternGuard (dev) · ModelArmorGuard (fails closed) · GuardChain
│   ├── model_gateway/             VertexStructuredExtractor (Gemini, response schema with JSON-mode fallback) ·
│   │   └── prompts/               DocumentAIReader · Word/Excel/text readers · PromptRegistry (versioned .md) · GuardedExtractor
│   ├── platform/                  the data platform as the agents see it: gold table registry (schema.py, the contract
│   │                              with the data team) · gold clients (in-memory, BigQuery) with the staleness guard ·
│   │                              files by pointer and hash · evidence stores · outcome sinks
│   ├── dispatch.py                WorkItem · dispatchers (inline, Pub/Sub) · work queues (in-memory, Pub/Sub pull)
│   ├── wiring.py                  builders both runtimes share (model stack, stores, platform clients)
│   ├── rules/                     reason-code catalogue (68 codes) · rule engine · composite confidence
│   ├── review/                    review queue (memory | Mongo) and its API router (scoped per agent)
│   ├── audit/                     append-only audit store (memory | Mongo)
│   ├── evaluation/                Order Intake and pre-bill scorecards · `python -m factory.evaluation`
│   └── observability/             OpenTelemetry → Cloud Trace · kill switch · operations API router (incl. sweep)
├── order_intake_agent/            models · OrderIntakePolicy (mode primary | fallback) · connectors (protocols ·
│                                  gold.py over the platform · stubs.py in memory) · steps a1..a10 · pipeline (gate,
│                                  manual-queue exits, exactly-once, incompletion log) · outcomes.py · case store · runtime
├── prebill_agent/                 canonical schema · normalise · five rules with verdicts · outcome labels and owners
│                                  per redline v2 · connectors (read-only: gold.py, landing.py, extracts.py, stubs.py) ·
│                                  steps b1..b8 · pipeline (recheck) · outcomes.py · Kraft Heinz fixtures · runtime
├── app/                           main.py (api: events, review, ops) · worker.py (pull and run) · push_auth.py (Pub/Sub OIDC) ·
│                                  routers/events.py · runtime.py (per-agent runtimes, dispatcher, sweeper) · auth · config
├── tests/                         no cloud needed: factory/, platform/, order_intake/, prebill/, api, events, worker
├── Ingredion_docs/                client documents, redline v2 diagrams, workflow and data-architecture pages, PDFs, tools
├── requirements.txt · requirements-gcp.txt · requirements-dev.txt · pyproject.toml · Dockerfile · .env.example
```

## Quick start

```bash
cd Ingredion
python -m venv .venv && .venv\Scripts\activate       # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                                                # stubs and a fake model, in memory
python -m factory.evaluation prebill                  # Kraft Heinz anchor 4/4, clean invoice, converted units
copy .env.example .env                                # set INGREDION_API_KEY at least
uvicorn app.main:app --reload --port 8100             # docs at /docs; both agents, cases run inline
```

Without a work topic the api runs each accepted case inline, so a laptop needs one
process. In the project the same image runs four Cloud Run services: `api` and
`worker` per agent (`python -m app.worker --agent order-intake|prebill`), joined by
the agent's work topic. The service boots with in-memory stores, the Dev stubs and
Vertex AI as the model (any model call answers "unavailable" until
`GOOGLE_CLOUD_PROJECT` and credentials exist). `INGREDION_PLATFORM=gold` switches
the reads to the gold tables; `INGREDION_MONGO_URI` makes the stores shared; the
Google Cloud SDKs are in `requirements-gcp.txt`.

## How a case moves

**Ingress.** The data platform's change signals arrive as Pub/Sub pushes on
`/events/order-intake/cases` (`gold.cases.changed`) and `/events/prebill/invoices`
(`gold.orders.invoice_ready`), signed with an OIDC token the api verifies against the
subscription's service account. The api refuses while the kill switch is engaged
(503, Pub/Sub retries later), claims the case once (a redelivery is acknowledged
without a second run), publishes a `WorkItem` to the agent's work topic and answers
204. `POST /api/<agent>/ops/poll` sweeps the gold intake table for anything the
signal missed. The worker pulls, keeps the lease extended while a case runs, and
acknowledges on success; a case that failed before the gate is re-run from A1 or B1
on redelivery, a case already at the gate is acknowledged, a stale gold table or an
engaged kill switch is a nack with a pause.

**Agent A** (`order_intake_agent/pipeline.py`): A1 pick up → A2 classify (Gemini:
new order, revised PO, duplicate or not an order; language; multi-PO split) → A3 read
the PO (Document AI text and token confidence for scans, Gemini in a fixed response
schema; one re-read on a hard failure) → A4 map to SAP and validate (customer,
CMIR and unit conversions from gold) → A5 rules and confidence (price and contract
from gold, duplicates against gold sales orders, ATP live, composite confidence) →
A6 exceptions (Gemini drafts the clarification for the flags that need the buyer;
saved as an Outlook draft via Graph; template fallback) → A7 review summary →
**human gate** → A8 payload → A9 create the order (write-ahead `submitting` state,
idempotency key `case:PO`, lookup in gold then live before any retry, 3 retries,
then the SAP incompletion log) → A10 Salesforce case with the outcome marker and the
incompletion follow-ups. Exits at A2, A4, A6, the gate and A9 go to the manual
queue with a reason code on the case. After a correction, A4 and A5 run again; a new
flag sends the case back to the queue. Every terminal state writes one
`case_outcome` row (and `field_corrections` rows after a correction).

**Agent B** (`prebill_agent/pipeline.py`): B1 pick up the draft invoice → B2 assemble
evidence (billing document, delivery, PROS or SAP condition price, contract terms,
freight and surcharge schedules, dispute history; snapshot kept per version) → B3
read the PO (Ariba from gold, then the PO captured on the Salesforce order, then a PO
PDF from the files bucket through Document AI and Gemini) → B4 normalise units and
currency, pair lines → B5 the checks with "which source wins" verdicts → Matched:
B8 record; otherwise B6 explain and draft (Gemini, template fallback) → B7 route to
the owner named for the outcome → **human gate** → B8 record (audit record plus one
`prebill_outcome` row per version). `recheck()` runs from B2 when the updated PO
arrives and closes the case when aligned.

## Invariants the code enforces

- Only `a6_exceptions` (Outlook draft), `a9_create_order` and `a10_update_case` call a
  write method on an Ingredion system; the pre-bill connector protocols have no write
  methods at all (tested). The agents' own writes are the evidence bucket, the
  outcomes dataset, the review queue and the audit trail.
- The agents read gold only. Every lookup names a table and columns in
  `factory/platform/schema.py`; an unknown table or column raises, and the
  connectors never issue free SQL. Before a table is read the staleness guard checks
  `ops.freshness` against the table's limit and raises `GoldStale` (the worker
  retries later). Files are fetched by pointer and verified against the SHA-256 on
  the gold row. The refresh times used go into the evidence snapshot and the
  outcome row.
- Every model call goes through `GuardedExtractor`: the guard chain (Model Armor in
  the project, the pattern guard always) screens every string input, and the prompt
  reference and SHA-256, model, tokens, latency and guard verdicts land in the audit
  record and in the evidence bucket with the raw answer. Prompts are versioned files.
- Gemini answers in a fixed response schema (translated for Gemini's dialect, with a
  JSON-mode fallback) and is validated by the Pydantic model either way; no tools.
- The reason-code catalogue (`factory/rules/reason_codes.py`) is closed; an unknown
  code raises. State transitions outside the table raise. A case left in
  `submitting` is looked up in SAP before anything else runs on restart.
- The audit store has no update or delete method. An evidence or outcome write that
  fails is logged and alerted, never allowed to fail the case.
- The kill switch stops new cases immediately (events answer 503, the sweep halts,
  the worker nacks, `process()` refuses); in-flight cases finish or return.

## HTTP API

`/api` routes need `X-API-Key: <INGREDION_API_KEY>` and `X-User-Id: <caller>` (the
reviewer identity; single sign-on maps onto it in the client project). `/events`
routes need the Pub/Sub push OIDC token (or the service key in Dev). Errors are
`{"error": "...", "success": false}`. `<agent>` is `order-intake` or `prebill`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/events/order-intake/cases` | Pub/Sub push: a case changed in `gold_cases.email_order_case`; claims and dispatches, 204 |
| `POST` | `/events/prebill/invoices` | Pub/Sub push: an order became invoice-ready; claims and dispatches, 204 |
| `GET` | `/api/<agent>/review/items?status=open&owner=` | The agent's review queue |
| `GET` | `/api/<agent>/review/items/{id}` | One item: fields, confidence, candidates, flags, drafts |
| `POST` | `/api/<agent>/review/items/{id}/decision` | `{"kind": "approve"\|"correct"\|"reject", "reason", "corrections": {...}, "confirmed_duplicate"}`; resumes the pipeline |
| `GET`/`POST` | `/api/<agent>/ops/kill-switch` | Status; `{"engaged": true, "reason": "..."}` to stop new cases |
| `POST` | `/api/<agent>/ops/poll` | One sweep of the intake table: claims and dispatches anything the signal missed |
| `GET` | `/api/<agent>/ops/health` | Kill switch state and audit record count |
| `GET` | `/health` | Liveness, no auth |

Correction keys for Agent A: `po_number`, `sold_to`, `ship_to`, `bill_to`,
`requested_delivery_date`, `currency`, `sold_to_id` / `ship_to_id` / `bill_to_id`
(pin an SAP partner), `line<N>.sap_material`, `line<N>.sales_uom`, `line<N>.quantity`,
`line<N>.uom`, `line<N>.unit_price`.

## Configuration

| Variable | Used by | Purpose |
|---|---|---|
| `INGREDION_API_KEY` | api | Shared service secret; the service refuses to start without it |
| `INGREDION_AGENTS` | api | Agents this instance serves: `order-intake,prebill` (default both) |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | Vertex AI, Pub/Sub, Cloud Trace | The Ingredion project and region |
| `VERTEX_MODEL`, `VERTEX_CONTROLLED_GENERATION` | Vertex AI | Allow-listed Gemini model (default `gemini-3.8-flash`); response schema on/off |
| `MODEL_ARMOR_TEMPLATE` | guardrails | Full template name; without it only the pattern guard runs (Dev) |
| `DOCUMENT_AI_PROCESSOR` | layout reader | Full processor name for PDFs and scans |
| `INGREDION_PLATFORM` | connectors | `stub` (default) or `gold` |
| `GOLD_PROJECT`, `GOLD_DATASET_SUFFIX`, `GOLD_MAX_AGE_MINUTES` | gold readers | Where the gold datasets live, the data team's environment suffix, a global staleness override |
| `FILES_BUCKET` | both agents | PO files, contracts and rate files, read by pointer and hash |
| `EXTRACT_BUCKET` / `EXTRACT_DIR` | pre-bill | Extract landing for rate files and TermSync (takes precedence when set) |
| `EVIDENCE_BUCKET_<AGENT>` / `EVIDENCE_DIR_<AGENT>` | both agents | Evidence per agent (`ORDER_INTAKE`, `PREBILL`); unset = in memory |
| `OUTCOMES_DATASET_<AGENT>` | both agents | BigQuery outcomes dataset per agent; unset = in memory |
| `WORK_TOPIC_<AGENT>`, `WORK_SUBSCRIPTION_<AGENT>` | api, worker | Pub/Sub between the api and the worker; unset = inline (Dev) |
| `PUBSUB_PUSH_AUDIENCE`, `PUBSUB_PUSH_SERVICE_ACCOUNT` | api | OIDC verification of push deliveries; unset = the service key stands in (Dev) |
| `GRAPH_DRAFT_MAILBOX` | A6 | Shared mailbox the clarification drafts are created in |
| `ORDER_INTAKE_MODE` | Agent A | `primary` (default) or `fallback` |
| `INGREDION_MONGO_URI` | stores | Audit, review queue, claims, kill switch, cases |
| `INGREDION_KILL_SWITCH` | kill switch | `on` stops new cases without a database |
| `INGREDION_CORS_ORIGINS`, `LOG_LEVEL` | api | As before |

## What is deliberately not here yet

- The write path. `StubSalesforce`, `StubSAPOrderAPI` and `StubGraphMail` stand in for
  the three writes until the method is approved at Gate 2 (4 December 2026):
  synchronous through SAP API Management, or the asynchronous outbound command
  dataset with its acknowledgement. Live availability (ATP) is delegated to the same
  live SAP connector.
- The gold DDL. `factory/platform/schema.py` is Parkar's proposal from the data-team
  input of 26 October 2026; the data team's actual columns replace it table by table,
  and the contract tests say what else has to move.
- Cloud Build with the SOW 5.4 scans, Terraform for the services, topics,
  subscriptions (with dead-letter topics), buckets and service accounts.
- The review queue page on Cloud Run. The API is complete; the page is a Stage 2
  deliverable. Single sign-on; the API key plus `X-User-Id` stands in for it.
- Splitting multi-PO emails into child cases (flagged `EMAIL.MULTI_PO`, to confirm).
- The Order Intake backtest data: `factory.evaluation.score_order_intake` is ready;
  the 500-PO sample is Ingredion's to provide.

## Tests

`tests/factory/` covers the runtime and the Vertex AI, Model Armor and Document AI
adapters with fakes; `tests/platform/` the gold registry and clients (including the
SQL the BigQuery client renders), the staleness guard, files by hash, evidence
stores and outcome sinks, and what both pipelines leave behind; `tests/order_intake/`
runs the ten-step pipeline on a one-cohort world and again on the same world as gold
rows; `tests/prebill/` runs the Kraft Heinz anchor on stubs, on gold rows and on
landing-bucket extracts; `tests/test_events_api.py`, `tests/test_review_ops_api.py`,
`tests/test_api.py` and `tests/test_worker.py` cover the api and the worker end to
end through the inline dispatcher.
