"""Order Intake policy (redline v2, 20 October 2026).

``mode`` is the big switch: ``primary`` means the agent processes every email-order
case Salesforce routes to it, cohort by cohort, with the Existing RPA as the
transition fallback; ``fallback`` is the earlier design, where the agent only took
RPA-failed cases and routed on the recorded error. Changing a value is a reviewed
release, like a prompt change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class OrderIntakePolicy:
    mode: Literal["primary", "fallback"] = "primary"
    # Phase 1: every case stops at the human judgment gate. Phase 2 (high-confidence
    # cases skip the gate) is an Ingredion decision at Gate 5.
    review_every_case: bool = True
    supported_languages: tuple[str, ...] = ("en",)  # French POs are out of scope
    split_multi_po_emails: bool = True
    confidence_threshold: float = 0.80  # composite score below this flags the field
    max_sap_retries: int = 3  # retries after the first attempt, with increasing waits
    retry_backoff_seconds: tuple[float, ...] = (2.0, 5.0, 15.0)
    pause_after_consecutive_failures: int = 5  # SAP down for all cases: stop submitting
    duplicate_window_days: int = 30
    revalidate_after_correction: bool = True  # corrected values re-run A4 and A5
    max_prompt_chars: int = 60_000
    price_tolerance: float = 0.005  # absolute, in price units, after UOM conversion
    ambiguous_units: tuple[str, ...] = field(default=("TON", "TONS", "T", "TONNE", "TONNES"))
    draft_clarification_with_model: bool = True  # A6 on Vertex AI; template fallback
    create_outlook_drafts: bool = True  # A6 saves the draft in the shared mailbox via Graph
    read_incompletion_log: bool = True  # A9 reads SAP's incompletion log after creation
    # fallback mode only
    attempt_mapping_data_failures: bool = True
    attempt_sap_failures: bool = False
    attempt_max_load_failures: bool = False


# Kept for callers written against the first design.
Release1Policy = OrderIntakePolicy
