"""Evidence stores and outcome sinks on their own, then through both pipelines: what
each case leaves behind in the agent's bucket and in its outcomes dataset."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from oi_fixtures import build as build_oi
from oi_fixtures import make_case

from factory.intake import OI
from factory.platform import (
    BigQueryOutcomeSink,
    GcsEvidenceStore,
    InMemoryEvidenceStore,
    InMemoryOutcomeSink,
    LocalEvidenceStore,
    OutcomeWriteFailed,
)
from factory.review import Decision, DecisionKind
from prebill_agent.fixtures import B6_ANSWER, MATERIAL, PO_REF, kraft_heinz_world
from prebill_agent.fixtures import build as build_pb
from prebill_agent.schema import CanonicalDoc, CanonicalLine, Charge, DocType

# ── stores and sinks ─────────────────────────────────────────────────────────


def test_evidence_stores_name_objects_by_case_run_and_step(tmp_path):
    memory = InMemoryEvidenceStore()
    uri = memory.put("CASE-1", "A3/source_text.json", {"text": "PO 1", "model": SimpleNamespace()}, run_id="run-1")
    assert uri == "memory://evidence/CASE-1/run-1/A3/source_text.json"
    assert memory.read_json(uri)["text"] == "PO 1" and memory.names("CASE-1") == ["A3/source_text.json"]

    local = LocalEvidenceStore(tmp_path)
    uri = local.put("809-6862", "B2/evidence_v0.json", {"invoice": 1}, run_id="r")
    assert uri.startswith("file:///") and (tmp_path / "809-6862" / "r" / "B2" / "evidence_v0.json").read_text() == json.dumps({"invoice": 1}, indent=1)

    uploads = []

    class Blob:
        def __init__(self, path):
            self.path = path

        def upload_from_string(self, data, content_type):
            uploads.append((self.path, data, content_type))

    gcs = GcsEvidenceStore("ingredion-agent-a-evidence-dev", prefix="cases", client=SimpleNamespace(bucket=lambda name: SimpleNamespace(blob=Blob)))
    uri = gcs.put("CASE-1", "A8/sap_payload.json", b"{}", run_id="run-1")
    assert uri == "gs://ingredion-agent-a-evidence-dev/cases/CASE-1/run-1/A8/sap_payload.json"
    assert uploads == [("cases/CASE-1/run-1/A8/sap_payload.json", b"{}", "application/json")]


def test_outcome_sinks_record_rows_and_surface_bigquery_errors():
    memory = InMemoryOutcomeSink()
    memory.record("case_outcome", {"case_id": "CASE-1", "outcome": "AGENT_CREATED"})
    assert memory.last("case_outcome")["outcome"] == "AGENT_CREATED"

    inserted = []
    ok = SimpleNamespace(insert_rows_json=lambda table, rows: inserted.append((table, rows)) or [])
    BigQueryOutcomeSink("ingredion-dev", "agent_a_outcomes", client=ok).record("case_outcome", {"case_id": "CASE-1"})
    assert inserted == [("ingredion-dev.agent_a_outcomes.case_outcome", [{"case_id": "CASE-1"}])]
    bad = SimpleNamespace(insert_rows_json=lambda table, rows: [{"index": 0, "errors": ["no such field: nope"]}])
    with pytest.raises(OutcomeWriteFailed):
        BigQueryOutcomeSink("ingredion-dev", "agent_a_outcomes", client=bad).record("case_outcome", {"nope": 1})


# ── through Agent A ──────────────────────────────────────────────────────────


def _oi_with_platform():
    h = build_oi()
    h.ctx.evidence = InMemoryEvidenceStore()
    h.ctx.outcomes = InMemoryOutcomeSink()
    return h


def test_order_intake_leaves_its_evidence_and_one_outcome_row_per_case():
    h = _oi_with_platform()
    case = h.pipeline.process(make_case())
    assert h.ctx.evidence.names("CASE-1") == ["A2/a2_classify.v2.json", "A3/a3_extract.v1.json", "A3/source_text.json"]
    assert h.ctx.outcomes.rows == {}  # nothing is final at the gate

    case = h.pipeline.resume(case, Decision(kind=DecisionKind.APPROVE, reviewer="reviewer-1"))
    assert case.state == OI.CASE_UPDATED
    names = h.ctx.evidence.names("CASE-1")
    assert names[-2:] == ["A8/sap_payload.json", "A9/sap_order.json"]
    model_call = h.ctx.evidence.read_json(f"memory://evidence/CASE-1/{case.run_id}/A3/a3_extract.v1.json")
    assert model_call["prompt"] == "order_intake/a3_extract@v1" and model_call["data"]["po_number"] == "4500123" and model_call["guard"][0]["allowed"] is True
    assert set(case.data["evidence_uris"]) == {f"memory://evidence/CASE-1/{case.run_id}/{n}" for n in names}

    row = h.ctx.outcomes.last("case_outcome")
    assert row["outcome"] == "AGENT_CREATED" and row["order_number"] == "SO-1001" and row["reviewer"] == "reviewer-1"
    assert row["model_calls"] == 2 and row["po_number"] == "4500123" and row["sold_to"] == "100123" and row["cohort"] == "cohort-1"
    assert len(row["evidence_uris"]) == 5 and row["gold_refresh"] is None  # stubs: no gold tables involved
    assert "field_corrections" not in h.ctx.outcomes.rows
    assert "outcome.recorded" in h.events()


def test_a_correction_also_writes_field_correction_rows_and_a_return_writes_an_outcome():
    h = _oi_with_platform()
    case = h.pipeline.process(make_case())
    # a correction the document supports (a value not in the text would lower the confidence and re-park the case)
    h.pipeline.resume(case, Decision(kind=DecisionKind.CORRECT, reviewer="reviewer-2", corrections={"requested_delivery_date": "2026-11-15"}))
    corrections = h.ctx.outcomes.rows["field_corrections"]
    assert [(r["field"], r["corrected_value"], r["reviewer"]) for r in corrections] == [("requested_delivery_date", '"2026-11-15"', "reviewer-2")]
    assert h.ctx.outcomes.last("case_outcome")["outcome"] == "AGENT_ASSISTED"

    h2 = _oi_with_platform()
    h2.pipeline.resume(h2.pipeline.process(make_case()), Decision(kind=DecisionKind.REJECT, reviewer="reviewer-1", reason="not an order"))
    row = h2.ctx.outcomes.last("case_outcome")
    assert row["outcome"] == "RETURNED" and "REVIEW.REJECTED" in row["reason_codes"] and row["order_number"] is None


def test_a_broken_evidence_bucket_never_fails_the_case():
    class Broken:
        name = "broken"

        def put(self, *args, **kwargs):
            raise OSError("bucket unreachable")

    h = build_oi()
    h.ctx.evidence = Broken()
    case = h.pipeline.process(make_case())
    assert case.state == OI.IN_REVIEW and "evidence.write_failed" in h.events()
    assert h.alerts.raised and h.alerts.raised[0]["kind"] == "evidence_write_failed"


# ── through Agent B ──────────────────────────────────────────────────────────


def test_prebill_keeps_a_snapshot_per_version_and_writes_one_outcome_row_per_version():
    h = build_pb(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    h.ctx.evidence = InMemoryEvidenceStore()
    h.ctx.outcomes = InMemoryOutcomeSink()
    case = h.pipeline.process(h.world.ref)
    assert h.ctx.evidence.names("809-6862") == ["B2/evidence_v0.json", "B3/po_ariba.json", "B6/b6_explain.v1.json"]
    snapshot = h.ctx.evidence.read_json(f"memory://evidence/809-6862/{case.run_id}/B2/evidence_v0.json")
    assert snapshot["invoice"]["lines"][0]["unit_price"] == 47.0 and snapshot["reference"]["contract_terms_days"] == 120
    assert h.ctx.outcomes.rows == {}

    case = h.pipeline.resume(case, Decision(kind=DecisionKind.APPROVE, reviewer="pricing-lead", reason="confirmed"))
    row = h.ctx.outcomes.last("prebill_outcome")
    assert row["version"] == 0 and row["outcome"] == "INTERNAL_FIX_OR_MISSING_DATA"
    assert set(row["failed_checks"]) == {"unit_price", "fuel_surcharge", "quantity", "payment_terms"}
    assert json.loads(row["verdicts"])["payment_terms"] == "INTERNAL_FIX" and json.loads(row["gaps"])["quantity"]["difference"] == 250
    assert row["traceable"] is True and row["reviewer"] == "pricing-lead" and row["model_calls"] == 1 and row["po_source"] == "ariba"

    updated_po = CanonicalDoc(
        doc_type=DocType.PO, order_ref=PO_REF, source="ariba", currency="USD", payment_terms_days=120,
        lines=[CanonicalLine(line_no=1, material=MATERIAL, qty=170_250, qty_uom="LB", unit_price=47.0, price_uom="CWT")],
        charges=[Charge(type="fuel_surcharge", amount=300.0)],
    )
    h.world.sap.invoices["809-6862"].payment_terms_days = 120
    h.pipeline.recheck(case, updated_po)
    assert "B2/evidence_v1.json" in h.ctx.evidence.names("809-6862")
    rows = h.ctx.outcomes.rows["prebill_outcome"]
    assert [(r["version"], r["outcome"]) for r in rows] == [(0, "INTERNAL_FIX_OR_MISSING_DATA"), (1, "MATCHED")]
    assert rows[1]["failed_checks"] == [] and rows[1]["po_source"] == "updated_po"
