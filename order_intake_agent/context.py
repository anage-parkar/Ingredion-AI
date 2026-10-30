"""Everything a step may touch, in one place, injected by the pipeline.

Steps receive ``(case, ctx)`` and nothing else, so a step can be tested with stubs
and the real wiring (``runtime.py``) decides which connectors, model provider and
stores are used in Dev, Test and Prod.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from factory.audit import AuditTrail
from factory.case import Case
from factory.intake import ClaimRegistry
from factory.model_gateway import (
    LayoutReader,
    Prompt,
    PromptRegistry,
    StructuredExtractor,
    StructuredResult,
)
from factory.observability import KillSwitch
from factory.platform import JSON, EvidenceStore, OutcomeSink, refresh_snapshot
from factory.review import ReviewQueue
from factory.rules import CompositeConfidence

from . import AGENT
from .connectors import (
    Alerts,
    CaseQueue,
    FailureRecordReader,
    GraphMail,
    SalesforceCases,
    SAPMasterData,
    SAPOrderAPI,
    SAPOrders,
)
from .policy import OrderIntakePolicy


@dataclass
class OrderIntakeContext:
    salesforce: SalesforceCases
    sap_master: SAPMasterData
    sap_orders: SAPOrders
    sap_order_api: SAPOrderAPI
    extractor: StructuredExtractor  # already wrapped in GuardedExtractor
    layout_reader: LayoutReader
    audit: AuditTrail
    review_queue: ReviewQueue
    claims: ClaimRegistry
    prompts: PromptRegistry = field(default_factory=PromptRegistry)
    case_queue: CaseQueue | None = None  # primary mode intake
    failure_record: FailureRecordReader | None = None  # fallback mode intake
    graph: GraphMail | None = None  # Outlook drafts for the reviewer (A6)
    draft_mailbox: str = "orders@ingredion.example"
    kill_switch: KillSwitch | None = None
    alerts: Alerts | None = None
    evidence: EvidenceStore | None = None  # the agent's evidence bucket
    outcomes: OutcomeSink | None = None  # agent_a_outcomes
    policy: OrderIntakePolicy = field(default_factory=OrderIntakePolicy)
    confidence: CompositeConfidence | None = None
    sleep: Callable[[float], None] = time.sleep  # injectable so tests do not wait
    today: Callable[[], date] = date.today

    def __post_init__(self) -> None:
        if self.confidence is None:
            self.confidence = CompositeConfidence(threshold=self.policy.confidence_threshold)

    # ── helpers used by every step ────────────────────────────────────────────
    def log(self, case: Case, step: str, event: str, *, actor: str = "agent", model_call: dict[str, Any] | None = None, **data: Any) -> None:
        self.audit.append(case.case_id, AGENT, step, event, actor=actor, data=data, model_call=model_call, run_id=case.run_id)

    def alert(self, kind: str, message: str, **data: Any) -> None:
        if self.alerts is not None:
            self.alerts.raise_alert(kind, message, **data)

    def prompt(self, name: str) -> Prompt:
        return self.prompts.get(name)

    # ── evidence and outcomes ─────────────────────────────────────────────────
    def keep(self, case: Case, step: str, name: str, content: Any, *, content_type: str = JSON) -> str | None:
        """Store one artefact in the evidence bucket under the case and run; the URI is
        kept on the case. A store failure is logged and alerted, never fatal: the audit
        record already holds the decision."""
        if self.evidence is None:
            return None
        try:
            uri = self.evidence.put(case.case_id, f"{step}/{name}", content, content_type=content_type, run_id=case.run_id)
        except Exception as exc:
            self.log(case, step, "evidence.write_failed", name=name, error=f"{type(exc).__name__}: {exc}")
            self.alert("evidence_write_failed", f"case {case.case_id}: {name}: {exc}", case_id=case.case_id)
            return None
        case.data.setdefault("evidence_uris", []).append(uri)
        return uri

    def keep_model_call(self, case: Case, step: str, result: StructuredResult) -> str | None:
        name = result.prompt_ref.rsplit("/", 1)[-1].replace("@", ".") + ".json"
        return self.keep(case, step, name, result.evidence())

    def gold_refresh(self) -> dict[str, str | None]:
        """Refresh times of every gold table the connectors used so far (empty on stubs)."""
        return refresh_snapshot(self.case_queue, self.salesforce, self.sap_master, self.sap_orders)

    def record_outcome(self, case: Case) -> None:
        """One row per finished case into the outcomes dataset (plus the field corrections)."""
        if self.outcomes is None:
            return
        from .outcomes import case_outcome_row, field_correction_rows

        try:
            self.outcomes.record("case_outcome", case_outcome_row(case, self))
            for row in field_correction_rows(case):
                self.outcomes.record("field_corrections", row)
        except Exception as exc:
            self.log(case, "outcome", "outcome.write_failed", error=f"{type(exc).__name__}: {exc}")
            self.alert("outcome_write_failed", f"case {case.case_id}: {exc}", case_id=case.case_id)
            return
        self.log(case, "outcome", "outcome.recorded", sink=getattr(self.outcomes, "name", "?"), outcome=case.outcome)
