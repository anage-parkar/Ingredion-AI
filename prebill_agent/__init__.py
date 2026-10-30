"""Pre-bill Validation and Dispute Prevention Agent (use case 2).

Runs between shipment and invoice submission. Eight steps, B1 to B8, on the shared
factory runtime; generative AI in B3 (reading a PDF PO when no structured PO exists)
and B6 (explaining the gaps and drafting the request) only. Rules decide, a person
acts. The agent writes to no Ingredion system: its outputs are the review queue,
the drafted request and the audit trail.
"""

from factory import AGENT_PREBILL as AGENT

__all__ = ["AGENT"]
