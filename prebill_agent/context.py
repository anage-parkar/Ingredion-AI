"""Everything a pre-bill step may touch. Note what is absent: there is no write
connector to an Ingredion system. The identity behind these readers has read roles
only; the agent's own writes are its evidence bucket and its outcomes dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
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

from . import AGENT
from .connectors import PROS, Ariba, Mailbox, RateFiles, SalesforceOrders, SAPBilling, TermSync
from .normalise import FxRates
from .policy import PrebillPolicy


@dataclass
class PrebillContext:
    sap: SAPBilling
    pros: PROS
    salesforce: SalesforceOrders
    ariba: Ariba
    termsync: TermSync
    rate_files: RateFiles
    extractor: StructuredExtractor  # guarded
    layout_reader: LayoutReader
    audit: AuditTrail
    review_queue: ReviewQueue
    claims: ClaimRegistry
    mailbox: Mailbox | None = None
    fx: FxRates | None = None
    prompts: PromptRegistry = field(default_factory=PromptRegistry)
    kill_switch: KillSwitch | None = None
    evidence: EvidenceStore | None = None  # the agent's evidence bucket
    outcomes: OutcomeSink | None = None  # agent_b_outcomes
    policy: PrebillPolicy = field(default_factory=PrebillPolicy)

    def log(self, case: Case, step: str, event: str, *, actor: str = "agent", model_call: dict[str, Any] | None = None, **data: Any) -> None:
        self.audit.append(case.case_id, AGENT, step, event, actor=actor, data=data, model_call=model_call, run_id=case.run_id)

    def prompt(self, name: str) -> Prompt:
        return self.prompts.get(name)

    # ── evidence and outcomes ─────────────────────────────────────────────────
    def keep(self, case: Case, step: str, name: str, content: Any, *, content_type: str = JSON) -> str | None:
        """Store one artefact in the evidence bucket under the case and run (a recheck
        is a new run id, so every version keeps its own snapshot)."""
        if self.evidence is None:
            return None
        try:
            uri = self.evidence.put(case.case_id, f"{step}/{name}", content, content_type=content_type, run_id=case.run_id)
        except Exception as exc:
            self.log(case, step, "evidence.write_failed", name=name, error=f"{type(exc).__name__}: {exc}")
            return None
        case.data.setdefault("evidence_uris", []).append(uri)
        return uri

    def keep_model_call(self, case: Case, step: str, result: StructuredResult) -> str | None:
        name = result.prompt_ref.rsplit("/", 1)[-1].replace("@", ".") + ".json"
        return self.keep(case, step, name, result.evidence())

    def gold_refresh(self) -> dict[str, str | None]:
        return refresh_snapshot(self.sap, self.pros, self.salesforce, self.ariba, self.termsync, self.rate_files, self.mailbox)

    def record_outcome(self, case: Case) -> None:
        """One ``prebill_outcome`` row per recorded version of the order."""
        if self.outcomes is None:
            return
        from .outcomes import prebill_outcome_row

        try:
            self.outcomes.record("prebill_outcome", prebill_outcome_row(case, self))
        except Exception as exc:
            self.log(case, "B8", "outcome.write_failed", error=f"{type(exc).__name__}: {exc}")
            return
        self.log(case, "B8", "outcome.recorded", sink=getattr(self.outcomes, "name", "?"), outcome=case.outcome, version=case.data.get("recheck_count", 0))
