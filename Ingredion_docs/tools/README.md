# Regenerating the PDFs

Both PDFs in `Ingredion_docs/` are generated; edit the sources, not the PDFs.

| PDF | Source | Command |
|---|---|---|
| `Ingredion_Agent_Workflows.pdf` | `ingredion-agent-workflows.html` | `python tools/build_workflow_pdf.py ingredion-agent-workflows.html <work dir> Ingredion_Agent_Workflows.pdf` |
| `Ingredion_Client_Requirements.pdf` | content inside `tools/build_requirements_pdf.py` | `python tools/build_requirements_pdf.py Ingredion_Client_Requirements.pdf` |

Needs Google Chrome (the workflow build prints through it), `pypdf` and `reportlab`
(`pip install pypdf reportlab`; `pypdfium2` only for `render_pages.py`, which renders
pages to PNG for a visual check). Run from `Ingredion_docs/`.

`build_guides/` generates the two Word build guides (`Build-Guide-Agent-A-Email-Order-Intake.docx`,
`Build-Guide-Agent-B-Prebill-Validation.docx`) with docx-js: the content lives in `agent_a.js`,
`agent_b.js` and `shared.js`, the dates are computed from Week 0 = 26 October 2026 in `lib.js`.
`cd tools/build_guides && npm install && node build.js ..` rewrites both files into `Ingredion_docs/`.
Word asks to update fields on first open so the contents table fills (or press F9).

`rpa_error_analysis.py` reads Ingredion's `NA NoTouch Error Analysis - ShipTo.xlsx` (needs
`openpyxl`) and prints the Stage 1 baseline tables: the 16 RPA error types reconciled against
`order_intake_agent/rpa_errors.py`, the split by failure point and agent step, the ship-to
concentration, weekly volumes, the no-touch baseline and data-quality notes.
`python tools/rpa_error_analysis.py "NA NoTouch Error Analysis - ShipTo.xlsx" --markdown rpa-failure-analysis-tables.md`
regenerates the tables file; README section 11 carries the narrative.

Note for this machine: the `backend-2/.venv` copy of reportlab has a cloud-only
placeholder file under OneDrive (`reportlab/pdfbase/acroform.py`), so the scripts were
run with a local `pip install --target` copy on `PYTHONPATH`. Pinning the venv folder to
"Always keep on this device" or moving the repo off OneDrive removes the need.

`kickoff_deck/` generates the kick-off presentation
(`Kickoff_ppt/Ingredion_Agentic_AI_Factory_Project_Kickoff.pptx`, 19 slides) with pptxgenjs, in the
theme of the earlier Parkar deck in the same folder. Slide content lives in `build_kickoff.js`;
`media/` holds the two logos and the cover artwork taken from that deck.
`cd tools/kickoff_deck && npm install && node build_kickoff.js "../../Kickoff_ppt/Ingredion_Agentic_AI_Factory_Project_Kickoff.pptx"`
rewrites the file. `render.ps1 -Deck <pptx> -OutDir <folder>` exports every slide to PNG through a
hidden PowerPoint instance for a visual check (Windows with PowerPoint installed; it closes only the
PowerPoint process it started).

`ingredion-data-architecture.html` (in `Ingredion_docs/`) is the data and integration architecture
page written after the data team's input of 26 October 2026: the agents read from the gold layer of the
Ingredion GCP medallion platform (Acersoft → landing → bronze → silver → gold) and write back through
an outbound path or API Management. It is hand-written HTML with inline SVG, no generator; a PDF can be
printed from it the same way as the workflow page (`build_workflow_pdf.py <html> <work dir> <pdf>`).

`ingredion-factory-and-gold-flow.html` (in `Ingredion_docs/`) answers two engineering questions against the code of 30 October 2026: what kind of layer `factory/` is (governance, agent ops and runtime in one package, with every module mapped) and how the agents read gold data from BigQuery and Cloud Storage (Lookup → staleness guard → parameterised SELECT → Pydantic models; files by pointer and hash; evidence and outcome write-back; inputs and outputs per connector method). Hand-written HTML with inline SVG, same tokens as the other two pages; no build step.
