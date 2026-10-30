"""Email Order Intake Agent (SOW No. 07 Part A): the primary processor for the
email-order cases Salesforce routes to it, cohort by cohort.

Ten steps, A1 to A10, as thin modules on the shared factory runtime. Generative AI
is used in A2 (classify), A3 (extract) and A6 (draft the clarification). Every case
stops at the human gate in Phase 1. A6 (an Outlook draft only), A9 (the SAP order)
and A10 (the Salesforce case) are the only modules that write to an Ingredion
system, after a reviewer approves.
"""

from factory import AGENT_ORDER_INTAKE as AGENT

__all__ = ["AGENT"]
