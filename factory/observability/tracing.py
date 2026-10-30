"""End-to-end tracing of every case: OpenTelemetry into Cloud Trace when the project
is configured, a no-op with debug logging otherwise. Nothing here imports
OpenTelemetry at module load, so the runtime works without the SDK installed.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .. import settings

logger = logging.getLogger("factory.trace")
_tracer: Any = None
_configured = False


def configure_tracing(service_name: str = "ingredion-factory") -> bool:
    """Set up OpenTelemetry with the Cloud Trace exporter. Returns True when a real
    tracer is active."""
    global _tracer, _configured
    if _configured:
        return _tracer is not None
    _configured = True
    try:
        from opentelemetry import trace
    except ImportError:
        logger.info("opentelemetry not installed; tracing is a no-op")
        return False
    project, _ = settings.gcp()
    if project:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
            provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter(project_id=project)))
            trace.set_tracer_provider(provider)
        except ImportError:
            logger.warning("opentelemetry-exporter-gcp-trace not installed; spans stay local")
    _tracer = trace.get_tracer(service_name)
    return True


class Span:
    """What steps see: a place to put attributes, whichever backend is active."""

    def __init__(self, name: str, attributes: dict[str, Any], otel_span: Any = None) -> None:
        self.name = name
        self.attributes = attributes
        self._otel = otel_span

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value
        if self._otel is not None:
            try:
                self._otel.set_attribute(key, value)
            except Exception:  # attribute type not supported by the exporter
                self._otel.set_attribute(key, str(value))


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    started = time.perf_counter()
    if _tracer is not None:
        with _tracer.start_as_current_span(name) as otel_span:
            wrapper = Span(name, dict(attributes), otel_span)
            for key, value in attributes.items():
                wrapper.set(key, value)
            yield wrapper
        return
    wrapper = Span(name, dict(attributes))
    try:
        yield wrapper
    finally:
        logger.debug("%s %s %.1fms", name, wrapper.attributes, (time.perf_counter() - started) * 1000)
