"""Layout and text extraction in front of the model.

Plain text, CSV and Excel readers cover email bodies and spreadsheet POs without a
cloud call; ``document_ai.py`` adds Document AI for PDFs and scans and a Word reader.
The mean token confidence a reader reports is one of the signals the composite
confidence score uses (see ``factory.rules.confidence``); readers with no notion of
it return ``None`` and the score relies on the other signals.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Protocol


class UnsupportedContent(RuntimeError):
    pass


@dataclass
class LayoutResult:
    text: str
    reader: str
    pages: int = 1
    tables: list[list[list[str]]] = field(default_factory=list)
    mean_confidence: float | None = None  # None when the reader has no notion of it


class LayoutReader(Protocol):
    name: str

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult: ...


def _decode(content: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class PlainTextReader:
    name = "plain_text"
    _TYPES = ("text/plain", "text/markdown", "text/html", "message/rfc822", "application/json")

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult:
        ctype = (content_type or "").split(";")[0].strip().lower()
        if ctype == "text/csv" or filename.lower().endswith(".csv"):
            text = _decode(content)
            rows = [row for row in csv.reader(io.StringIO(text)) if row]
            return LayoutResult(text=text, reader=self.name, tables=[rows] if rows else [])
        if ctype in self._TYPES or ctype.startswith("text/") or filename.lower().endswith((".txt", ".md")):
            return LayoutResult(text=_decode(content), reader=self.name)
        raise UnsupportedContent(f"{self.name} cannot read {content_type or filename!r}")


class ExcelReader:
    """``.xlsx`` via openpyxl (optional dependency); every sheet becomes a table."""

    name = "excel"
    _TYPES = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult:
        ctype = (content_type or "").split(";")[0].strip().lower()
        if ctype not in self._TYPES and not filename.lower().endswith(".xlsx"):
            raise UnsupportedContent(f"{self.name} cannot read {content_type or filename!r}")
        try:
            import openpyxl
        except ImportError as exc:
            raise UnsupportedContent("openpyxl is not installed; add it to read Excel POs") from exc
        book = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        tables: list[list[list[str]]] = []
        lines: list[str] = []
        for sheet in book.worksheets:
            rows = [["" if c is None else str(c) for c in row] for row in sheet.iter_rows(values_only=True)]
            rows = [r for r in rows if any(cell.strip() for cell in r)]
            if rows:
                tables.append(rows)
                lines.append(f"## {sheet.title}")
                lines.extend("\t".join(r) for r in rows)
        return LayoutResult(text="\n".join(lines), reader=self.name, pages=len(tables), tables=tables)


class CompositeReader:
    """First reader that accepts the content wins; raises if none does."""

    name = "composite"

    def __init__(self, readers: list[LayoutReader]) -> None:
        self.readers = readers

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult:
        errors: list[str] = []
        for reader in self.readers:
            try:
                return reader.read(content, content_type, filename=filename)
            except UnsupportedContent as exc:
                errors.append(str(exc))
        raise UnsupportedContent("; ".join(errors) or "no reader configured")
