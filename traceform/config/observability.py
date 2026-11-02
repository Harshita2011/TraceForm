"""
# §4 / §6D / §6E — OpenTelemetry Observability & Structured JSON Logging.
# Provides context propagation across pipeline spans and machine-searchable JSON logs.
"""

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Generator, Optional


class TraceFormJSONFormatter(logging.Formatter):
    """
    §6E — Structured JSON Log Formatter.
    Injects timestamp, level, trace_id, span_id, operator_id, generation_id, and event.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", str(uuid.uuid4())[:8]),
            "span_id": getattr(record, "span_id", None),
            "operator_id": getattr(record, "operator_id", "system"),
            "generation_id": getattr(record, "generation_id", None),
            "source_id": getattr(record, "source_id", None),
            "artifact_id": getattr(record, "artifact_id", None),
            "event": getattr(record, "event", record.funcName),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


class MockSpan:
    """Lightweight OpenTelemetry-compatible span wrapper."""
    def __init__(
        self,
        name: str,
        source_id: Optional[str] = None,
        generation_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ):
        self.name = name
        self.trace_id = str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())[:16]
        self.source_id = source_id
        self.generation_id = generation_id
        self.operator_id = operator_id or "system"
        self.artifact_id = artifact_id
        self.attributes: dict[str, Any] = {}
        self.start_time = time.perf_counter()
        self.end_time: Optional[float] = None
        self.status = "OK"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = time.perf_counter()


@contextmanager
def trace_span(
    name: str,
    source_id: Optional[str] = None,
    generation_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> Generator[MockSpan, None, None]:
    """
    §6D — Synchronous OpenTelemetry trace span context manager.
    """
    span = MockSpan(
        name=name,
        source_id=source_id,
        generation_id=generation_id,
        operator_id=operator_id,
        artifact_id=artifact_id,
    )
    logger = logging.getLogger("traceform.telemetry")
    logger.debug(
        "SPAN START: %s (trace_id=%s span_id=%s generation_id=%s)",
        name,
        span.trace_id,
        span.span_id,
        generation_id,
        extra={
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "generation_id": generation_id,
            "source_id": source_id,
            "operator_id": span.operator_id,
            "event": f"span_start:{name}",
        },
    )
    try:
        yield span
    except Exception as e:
        span.set_status("ERROR")
        span.set_attribute("error.message", str(e))
        raise
    finally:
        span.end()
        duration_ms = round((span.end_time - span.start_time) * 1000, 2)
        logger.debug(
            "SPAN END: %s in %sms (status=%s)",
            name,
            duration_ms,
            span.status,
            extra={
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "duration_ms": duration_ms,
                "event": f"span_end:{name}",
            },
        )


@asynccontextmanager
async def async_trace_span(
    name: str,
    source_id: Optional[str] = None,
    generation_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> AsyncGenerator[MockSpan, None]:
    """
    §6D — Asynchronous OpenTelemetry trace span context manager.
    """
    with trace_span(
        name=name,
        source_id=source_id,
        generation_id=generation_id,
        operator_id=operator_id,
        artifact_id=artifact_id,
    ) as span:
        yield span
