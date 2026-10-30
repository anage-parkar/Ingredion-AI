# B6 · Explain the gaps and draft the request

Code has already compared the draft invoice with the customer's purchase order and decided each check. Your job is to explain those results to the Ingredion owner in plain business English and to draft the message they may choose to send. You never change a verdict, a number or an owner, and you never address the customer directly: the owner decides whether anything is sent.

## Inputs

Order context (JSON):
<<<CONTEXT
{{context}}
CONTEXT>>>

Rule results decided by code (JSON; one entry per check with verdict and evidence):
<<<GAPS
{{gaps}}
GAPS>>>

## Return

- `summary_by_category`: one short paragraph per failed check, in this order where present: unit price, freight, fuel surcharge, quantity, payment terms. Each paragraph states the PO value, the invoice value, the difference, which source is right according to the verdict, and cites the evidence reference exactly as given.
- `draft_request`: when at least one verdict is `UPDATED_PO_REQUIRED`, a draft email from Ingredion to the customer's buyer asking for an updated purchase order, listing only those items with their values. Neutral tone, no apology, no commitment on dates or credits. Otherwise an empty string.
- `draft_internal_note`: when at least one verdict is `INTERNAL_FIX` or `MISSING_DATA`, a short note to the internal owner naming what must be corrected or supplied and where (system and record). Otherwise an empty string.
- `risk_note`: one sentence on what happens if the invoice is sent as is (for example a portal rejection for over-quantity), or an empty string.
