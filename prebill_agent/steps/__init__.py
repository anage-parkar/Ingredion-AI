"""One module per SOW step: B1 pick up · B2 assemble evidence · B3 read the PO
(model, fallback) · B4 normalise · B5 compare (rules) · B6 explain and draft (model)
· B7 route to the owner · B8 record. Each exposes ``run(case, ctx) -> StepResult``."""
