### Error categories: Ingredion's count, ours from the raw messages, and where the agent absorbs each

| Category | Ingredion | Classifier | Share | Failure point | Agent step | Addressed | Reason code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Customer Material Not Available | 277 | 277 | 23.5% | Database | A4 | partly | MASTER.MATERIAL_NOT_FOUND |
| PO Already Created | 157 | 157 | 13.3% | SAP | A2 / A5 | routing | EMAIL.DUPLICATE_SUBMISSION |
| No Line Level Items | 130 | 146 | 12.4% | OCR | A2 / A3 | by design | EXTRACT.NO_LINES |
| Sum of Line Total Validation | 133 | 133 | 11.3% | OCR | A3 / A5 | by design | EXTRACT.LINE_TOTALS_MISMATCH |
| Multiple Customer Material Profiles | 119 | 119 | 10.1% | Database | A4 | partly | CMIR.MULTIPLE_MATCHES |
| Zero Quantity | 96 | 96 | 8.1% | OCR | A3 / A4 | by design | EXTRACT.ZERO_QUANTITY |
| Delivery Date Format | 54 | 63 | 5.3% | OCR | A3 | by design | EXTRACT.DATE_FORMAT |
| Missing Label Names | 50 | 50 | 4.2% | OCR | A3 | by design | EXTRACT.LOW_CONFIDENCE |
| Grand Total Not Numeric | 44 | 45 | 3.8% | OCR | A3 | by design | EXTRACT.NOT_NUMERIC |
| Customer Material Exists MAX Load | 32 | 32 | 2.7% | Database/OCR | A3 / A5 | partly | QTY.MAX_LOAD |
| Sales Order Number Not Generated | 18 | 18 | 1.5% | SAP | A9 | by design | SAP.RECONCILED |
| Label Values Not Extracted | 14 | 17 | 1.4% | OCR | A3 | by design | EXTRACT.LOW_CONFIDENCE |
| No Model ID | 14 | 14 | 1.2% | Database | A3 / A4 | by design | MASTER.SOLD_TO_NOT_FOUND |
| Unit Price Not Numeric | 11 | 11 | 0.9% | OCR | A3 | by design | EXTRACT.NOT_NUMERIC |
| Miscellaneous | 2 | 2 | 0.2% | Unknown | A1 | reported | EXTRACT.FORMAT_ERROR |
| Customer Mapping Missing | 29 | 0 | 0.0% | Database | A3 | by design | EXTRACT.NO_LINES |

Reconciliation differences (category, Ingredion, classifier): No Line Level Items: 130 vs 146; Delivery Date Format: 54 vs 63; Grand Total Not Numeric: 44 vs 45; Customer Mapping Missing: 29 vs 0; Label Values Not Extracted: 14 vs 17. Ingredion's 'Customer Mapping Missing' was assigned from the mapping database, not from the message text, so the classifier reports those cases under the extraction failure the message states; the other differences are concatenated messages where Ingredion's choice cannot be reproduced from the text alone.

### Failure point and what the agent does with it

| Failure point | Cases | Share |
| --- | --- | --- |
| OCR | 561 | 47.5% |
| Database | 410 | 34.7% |
| SAP | 175 | 14.8% |
| Database/OCR | 32 | 2.7% |
| Unknown | 2 | 0.2% |

| Addressed | Cases | Share | Meaning |
| --- | --- | --- | --- |
| by design | 593 | 50.3% | the agent does not have this failure mode |
| partly | 428 | 36.3% | resolved when the data exists in SAP; otherwise reported, not fixed |
| routing | 157 | 13.3% | not an order to create: classified and closed, or sent to the reviewer |
| reported | 2 | 0.2% | outside the agent; recorded on the case |

### Ship-tos with the most failures (cohort candidates)

| Ship-to | Customer (as on the case) | Failed cases | Cumulative share | Top error type (share of the ship-to) | Agent step | Addressed |
| --- | --- | --- | --- | --- | --- | --- |
| 2065 | Batory Foods (USCA HQ) | 127 | 11% | Zero Quantity (58%) | A3 / A4 | by design |
| 121465 | KEN'S FOODS, LLC | 83 | 18% | Sum of Line Total Validation (66%) | A3 / A5 | by design |
| 101372 | SWEETENER SUPPLY | 61 | 23% | PO Already Created (67%) | A2 / A5 | routing |
| 121058 | SKIDMORE SALES | 59 | 28% | Customer Material Not Available (39%) | A4 | partly |
| N/A | Kerry EMEA | 46 | 32% | No Model ID (28%) | A3 / A4 | by design |
| 1216 | Essex Food Ingredients (USCA HQ) | 44 | 36% | Sum of Line Total Validation (41%) | A3 / A5 | by design |
| 101671 | SWEETS MIX COMPANY INC | 44 | 39% | Grand Total Not Numeric (100%) | A3 | by design |
| 123064 | KERRY INGREDIENTS | 42 | 43% | No Line Level Items (67%) | A2 / A3 | by design |
| 124270 | ICI FOODS | 37 | 46% | Customer Material Not Available (43%) | A4 | partly |
| 125594 | INTERNATIONAL FOOD PRODUCTS | 32 | 49% | Multiple Customer Material Profiles (44%) | A4 | partly |
| 2263 | IFF (USCA HQ) | 19 | 50% | Delivery Date Format (89%) | A3 | by design |
| 131144 | BALDWIN RICHARD FOODS | 19 | 52% | Customer Material Not Available (89%) | A4 | partly |

### Failed cases per ISO week (date taken from the case number)

| Week | Failed cases |
| --- | --- |
| 2026-W22 | 16 |
| 2026-W23 | 89 |
| 2026-W24 | 97 |
| 2026-W25 | 79 |
| 2026-W26 | 107 |
| 2026-W27 | 128 |
| 2026-W28 | 181 |
| 2026-W29 | 158 |
| 2026-W30 | 94 |
| 2026-W31 | 231 |

### Ingredion's 'Current Breakdown' sheet (period as stated by Ingredion)

| Line | Value | Note |
| --- | --- | --- |
| Total Number of Cases | 4000 |  |
| Number of Errors | 1500 |  |
| Total Cases Run by Optimization Bot | 1344 |  |
| Cases Successfully Run by Optimization Bot | 120 | 735 |
| Cases Fixed by John then Successfully run by John and team | 615 |  |
| Cases That Had to be done manually anyway | 609 | This includes ~340 cases that failed even after all the data was added, and ~270 from various manual issues, initial runs where the last run was just done manually, and cases that were pulled as they were already manually entered |

| Derived rate | Value |
| --- | --- |
| No-touch rate (cases with no error / total) | 62.5% |
| Recovered by the optimization bot alone (of errors) | 8.0% |
| Recovered after a person fixed data (of errors) | 41.0% |
| Done manually anyway (of errors) | 40.6% |
| Cases that reached SAP without a person touching data (of total) | 65.5% |

### Data quality notes for the backtest sample

| Observation | Count |
| --- | --- |
| Records (all Status = Failed; no successes in the file) | 1180 |
| Distinct Customer names / after normalising spelling | 133 / 116 (12 names with several spellings) |
| Records with ship-to N/A | 46 |
| Messages where the bot ran a second attachment (terms and conditions) after a success | 84 |
| Messages carrying more than one failure type | 141 |
| Attachment type of the failing run | pdf: 1165, (no attachment name): 15 |
