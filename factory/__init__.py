"""Shared runtime for the Ingredion Agentic AI Factory.

Both agents, Email Order Intake (A1 to A10) and Pre-bill Validation (B1 to B8), are
thin step modules on top of this package. It holds everything the two SOWs describe
as common: case intake and the per-case state machine, guardrails in front of every
model call, the Vertex AI model gateway with versioned prompts, deterministic rules
and reason codes, the review queue (the human gate), the append-only audit trail,
the data-platform access (gold readers, evidence and outcome writers), the dispatch
between api and worker, the evaluation suite and the observability controls
(tracing, kill switch).

Nothing in this package imports from ``app``, ``order_intake_agent`` or
``prebill_agent``; the dependency arrow points one way.
"""

AGENT_ORDER_INTAKE = "order_intake"
AGENT_PREBILL = "prebill"
