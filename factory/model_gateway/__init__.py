"""Model gateway: the only place either agent talks to a model.

Versioned prompts, schema-enforced structured answers, guardrails in front of every
call, Document AI (or a plain reader) for layout, and Gemini on Vertex AI underneath,
in Ingredion's Google Cloud project (redline v2). Nothing here sends data to any
other provider.
"""

from .document_ai import DocumentAIReader, WordReader
from .errors import ModelUnavailable
from .layout import (
    CompositeReader,
    ExcelReader,
    LayoutReader,
    LayoutResult,
    PlainTextReader,
    UnsupportedContent,
)
from .prompts import PROMPTS_ROOT, Prompt, PromptNotFound, PromptRegistry, PromptRenderError
from .structured import (
    ExtractionFormatError,
    FakeStructuredExtractor,
    GuardedExtractor,
    StructuredExtractor,
    StructuredResult,
    parse_to_schema,
)
from .vertex import VertexStructuredExtractor, VertexUnavailable, gemini_schema

__all__ = [
    "PROMPTS_ROOT",
    "CompositeReader",
    "DocumentAIReader",
    "ExcelReader",
    "ExtractionFormatError",
    "FakeStructuredExtractor",
    "GuardedExtractor",
    "LayoutReader",
    "LayoutResult",
    "ModelUnavailable",
    "PlainTextReader",
    "Prompt",
    "PromptNotFound",
    "PromptRegistry",
    "PromptRenderError",
    "StructuredExtractor",
    "StructuredResult",
    "UnsupportedContent",
    "VertexStructuredExtractor",
    "VertexUnavailable",
    "WordReader",
    "gemini_schema",
    "parse_to_schema",
]
