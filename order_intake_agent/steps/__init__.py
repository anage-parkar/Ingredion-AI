"""One module per step of the redline v2 design. Each exposes ``run(case, ctx) ->
StepResult`` and never calls another step; the pipeline sequences them and owns the
state machine.

A1 pick up the case · A2 classify the email (Vertex AI) · A3 read the PO (Vertex AI +
Document AI) · A4 map to SAP and validate · A5 rules and confidence · A6 exceptions
(Vertex AI + Graph draft) · A7 review summary · human gate · A8 build the SAP payload
· A9 create the order (SAP write, then the incompletion log) · A10 update the case
(Salesforce write).
"""
