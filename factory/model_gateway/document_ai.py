"""Google Document AI (Enterprise Document OCR / layout) as the layout reader for
PDFs and scans, plus a Word reader for ``.docx`` POs.

Document AI returns the text, the tables and a confidence per token; the mean token
confidence is the layout signal in the composite confidence score. Word and Excel
documents are not OCR inputs, so they are read directly and the composite score
relies on the other signals for them.
"""

from __future__ import annotations

import io
from typing import Any

from .. import settings
from .layout import LayoutResult, UnsupportedContent

_DOC_AI_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/tif",
    "image/gif",
    "image/bmp",
    "image/webp",
}


class DocumentAIReader:
    name = "document_ai"

    def __init__(self, processor: str | None = None, *, client: Any = None) -> None:
        self.processor = processor or settings.document_ai_processor()
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.processor:
            raise UnsupportedContent("Document AI is not configured: set DOCUMENT_AI_PROCESSOR")
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import documentai
        except ImportError as exc:
            raise UnsupportedContent("google-cloud-documentai is not installed") from exc
        location = self.processor.split("/locations/")[1].split("/")[0] if "/locations/" in self.processor else "us"
        self._client = documentai.DocumentProcessorServiceClient(client_options=ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com"))
        return self._client

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult:
        ctype = (content_type or "").split(";")[0].strip().lower()
        if ctype not in _DOC_AI_TYPES and not filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")):
            raise UnsupportedContent(f"{self.name} does not read {content_type or filename!r}")
        client = self._get_client()
        try:
            from google.cloud import documentai

            request = documentai.ProcessRequest(name=self.processor, raw_document=documentai.RawDocument(content=content, mime_type=ctype or "application/pdf"))
        except ImportError:  # fake client in tests
            request = {"name": self.processor, "raw_document": {"content": content, "mime_type": ctype}}
        document = client.process_document(request=request).document
        text = getattr(document, "text", "") or ""
        pages = list(getattr(document, "pages", None) or [])
        tables: list[list[list[str]]] = []
        confidences: list[float] = []
        for page in pages:
            for table in getattr(page, "tables", None) or []:
                grid: list[list[str]] = []
                for row in list(getattr(table, "header_rows", []) or []) + list(getattr(table, "body_rows", []) or []):
                    grid.append([_anchor_text(text, cell.layout) for cell in row.cells])
                tables.append(grid)
            for token in getattr(page, "tokens", None) or []:
                conf = getattr(getattr(token, "layout", None), "confidence", None)
                if conf is not None:
                    confidences.append(float(conf))
        return LayoutResult(
            text=text,
            reader=self.name,
            pages=len(pages) or 1,
            tables=tables,
            mean_confidence=(sum(confidences) / len(confidences)) if confidences else None,
        )


def _anchor_text(full_text: str, layout: Any) -> str:
    anchor = getattr(layout, "text_anchor", None)
    segments = getattr(anchor, "text_segments", None) or []
    parts = []
    for seg in segments:
        start = int(getattr(seg, "start_index", 0) or 0)
        end = int(getattr(seg, "end_index", 0) or 0)
        parts.append(full_text[start:end])
    return "".join(parts).strip()


class WordReader:
    """``.docx`` via python-docx (optional dependency): paragraphs and tables."""

    name = "word"
    _TYPES = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",)

    def read(self, content: bytes, content_type: str, *, filename: str = "") -> LayoutResult:
        ctype = (content_type or "").split(";")[0].strip().lower()
        if ctype not in self._TYPES and not filename.lower().endswith(".docx"):
            raise UnsupportedContent(f"{self.name} cannot read {content_type or filename!r}")
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise UnsupportedContent("python-docx is not installed; add it to read Word POs") from exc
        document = docx.Document(io.BytesIO(content))
        lines = [p.text for p in document.paragraphs if p.text.strip()]
        tables: list[list[list[str]]] = []
        for table in document.tables:
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            rows = [r for r in rows if any(r)]
            if rows:
                tables.append(rows)
                lines.extend("\t".join(r) for r in rows)
        return LayoutResult(text="\n".join(lines), reader=self.name, tables=tables)
