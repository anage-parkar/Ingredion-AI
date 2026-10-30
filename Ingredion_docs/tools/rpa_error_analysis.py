"""Read Ingredion's "NA NoTouch Error Analysis - ShipTo.xlsx" and print the tables the
Stage 1 baseline (A-D1) and exception map (A-D2) start from: the error categories
reconciled against our classifier, the split by failure point and agent step, the
ship-to concentration, the weekly run-rate and the no-touch baseline.

    python tools/rpa_error_analysis.py "NA NoTouch Error Analysis - ShipTo.xlsx" [--markdown out.md]

Run from Ingredion_docs/ with the Ingredion package importable (PYTHONPATH=..). Needs openpyxl.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import openpyxl  # noqa: E402

from order_intake_agent.rpa_errors import (  # noqa: E402
    PROFILES,
    Addressed,
    RPAErrorType,
    classify_rpa_message,
)


def load(path: str):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    raw = list(wb["Raw Data"].iter_rows(values_only=True))
    hdr = [str(h) for h in raw[0]]
    rows = [dict(zip(hdr, r, strict=False)) for r in raw[1:] if r and r[2]]
    client = {}
    for r in wb["Overall Error Types"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            client[str(r[0]).strip()] = int(r[1])
    breakdown = []
    for r in wb["Current Breakdown"].iter_rows(values_only=True):
        cells = [html.unescape(str(v)) for v in r if v is not None]
        if cells:
            breakdown.append(cells)
    return rows, client, breakdown


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--markdown", help="write the tables to this file as well")
    args = ap.parse_args(argv)

    rows, client, breakdown = load(args.workbook)
    n = len(rows)
    errors = [classify_rpa_message(r["ErrorMessage"]) for r in rows]
    sections: list[str] = []

    # 1. categories reconciled with Ingredion's sheet
    ours = Counter(e.error_type for e in errors)
    cat_rows = []
    for t in sorted(RPAErrorType, key=lambda t: -ours[t]):
        p = PROFILES[t]
        cat_rows.append((t.value, client.get(t.value, ""), ours[t], f"{ours[t]/n:.1%}", p.failure_point.value, p.agent_step, p.addressed.value, p.reason_code))
    sections.append("### Error categories: Ingredion's count, ours from the raw messages, and where the agent absorbs each\n\n" + table(
        ["Category", "Ingredion", "Classifier", "Share", "Failure point", "Agent step", "Addressed", "Reason code"], cat_rows))
    mismatches = [(t.value, client.get(t.value), ours[t]) for t in RPAErrorType if client.get(t.value) != ours[t]]
    if mismatches:
        sections.append(
            "Reconciliation differences (category, Ingredion, classifier): " + "; ".join(f"{a}: {b} vs {c}" for a, b, c in mismatches)
            + ". Ingredion's 'Customer Mapping Missing' was assigned from the mapping database, not from the message text, so the classifier "
            "reports those cases under the extraction failure the message states; the other differences are concatenated messages where "
            "Ingredion's choice cannot be reproduced from the text alone."
        )

    # 2. split by failure point and by how the agent addresses it
    by_point = Counter(PROFILES[e.error_type].failure_point.value for e in errors)
    by_addr = Counter(PROFILES[e.error_type].addressed.value for e in errors)
    sections.append("### Failure point and what the agent does with it\n\n" + table(
        ["Failure point", "Cases", "Share"], [(k, v, f"{v/n:.1%}") for k, v in by_point.most_common()]) + "\n\n" + table(
        ["Addressed", "Cases", "Share", "Meaning"],
        [(k, v, f"{v/n:.1%}", {a.value: {
            Addressed.BY_DESIGN: "the agent does not have this failure mode",
            Addressed.PARTLY: "resolved when the data exists in SAP; otherwise reported, not fixed",
            Addressed.ROUTING: "not an order to create: classified and closed, or sent to the reviewer",
            Addressed.REPORTED: "outside the agent; recorded on the case",
        }[a] for a in Addressed}[k]) for k, v in by_addr.most_common()]))

    # 3. ship-to concentration
    by_ship = defaultdict(list)
    for r, e in zip(rows, errors, strict=True):
        by_ship[str(r["ShipTo"]).strip()].append((str(r["Customer"]).strip(), e.error_type))
    ship_rows = []
    cum = 0
    for ship, items in sorted(by_ship.items(), key=lambda kv: -len(kv[1]))[:12]:
        cum += len(items)
        top_type, top_n = Counter(t for _, t in items).most_common(1)[0]
        cust = Counter(c for c, _ in items).most_common(1)[0][0]
        ship_rows.append((ship, cust, len(items), f"{cum/n:.0%}", f"{top_type.value} ({top_n/len(items):.0%})", PROFILES[top_type].agent_step, PROFILES[top_type].addressed.value))
    sections.append("### Ship-tos with the most failures (cohort candidates)\n\n" + table(
        ["Ship-to", "Customer (as on the case)", "Failed cases", "Cumulative share", "Top error type (share of the ship-to)", "Agent step", "Addressed"], ship_rows))

    # 4. weekly run-rate from the case number date
    weeks = Counter()
    for r in rows:
        m = re.match(r"(\d{4})-(\d{2})(\d{2})-", str(r["CaseNumber"]))
        if m:
            weeks[datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%G-W%V")] += 1
    sections.append("### Failed cases per ISO week (date taken from the case number)\n\n" + table(["Week", "Failed cases"], sorted(weeks.items())))

    # 5. the no-touch baseline sheet
    sections.append("### Ingredion's 'Current Breakdown' sheet (period as stated by Ingredion)\n\n" + table(["Line", "Value", "Note"], [(b[0], b[1] if len(b) > 1 else "", b[2] if len(b) > 2 else "") for b in breakdown]))
    try:
        total = int(breakdown[0][1])
        errs = int(breakdown[1][1])
        bot_ok = int(breakdown[3][1])
        fixed = int(breakdown[4][1])
        manual = int(breakdown[5][1])
        sections.append(table(["Derived rate", "Value"], [
            ("No-touch rate (cases with no error / total)", f"{(total-errs)/total:.1%}"),
            ("Recovered by the optimization bot alone (of errors)", f"{bot_ok/errs:.1%}"),
            ("Recovered after a person fixed data (of errors)", f"{fixed/errs:.1%}"),
            ("Done manually anyway (of errors)", f"{manual/errs:.1%}"),
            ("Cases that reached SAP without a person touching data (of total)", f"{(total-errs+bot_ok)/total:.1%}"),
        ]))
    except (IndexError, ValueError):
        pass

    # 6. data quality
    multi = sum(1 for e in errors if e.multi_attachment)
    no_ship = sum(1 for r in rows if str(r["ShipTo"]).strip() == "N/A")
    names = Counter(str(r["Customer"]).strip() for r in rows)
    def norm(c):
        c = re.sub(r"[^A-Z0-9 ]", " ", c.upper())
        c = re.sub(r"\b(INC|LLC|CO|CORP|LTD|USCA HQ)\b", " ", c)
        return re.sub(r"\s+", " ", c).strip()
    groups = defaultdict(set)
    for c in names:
        groups[norm(c)].add(c)
    variants = sum(1 for v in groups.values() if len(v) > 1)
    exts = Counter((e.attachment or "").rsplit(".", 1)[-1].lower() if e.attachment else "(no attachment name)" for e in errors)
    also = sum(1 for e in errors if e.also)
    sections.append("### Data quality notes for the backtest sample\n\n" + table(["Observation", "Count"], [
        ("Records (all Status = Failed; no successes in the file)", n),
        ("Distinct Customer names / after normalising spelling", f"{len(names)} / {len(groups)} ({variants} names with several spellings)"),
        ("Records with ship-to N/A", no_ship),
        ("Messages where the bot ran a second attachment (terms and conditions) after a success", multi),
        ("Messages carrying more than one failure type", also),
        ("Attachment type of the failing run", ", ".join(f"{k}: {v}" for k, v in exts.most_common())),
    ]))

    text = "\n\n".join(sections)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text + "\n", encoding="utf-8")
        print(f"\nwritten {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
