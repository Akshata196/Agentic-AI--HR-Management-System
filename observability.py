
"""Lightweight, stdio-safe observability for MCP tools."""
import contextvars
import functools
import logging
import os
import time
import uuid
from collections import Counter
from typing import Any, Callable
from logging.handlers import RotatingFileHandler


log_level = os.getenv("LOG_LEVEL", "INFO").upper()

os.makedirs("logs", exist_ok=True)

file_handler = RotatingFileHandler(
    "logs/atliq_hr_assist.log",
    maxBytes=5_000_000,
    backupCount=3,
    encoding="utf-8",
)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        file_handler,
    ],
)

logger = logging.getLogger("atliq.hr_assist")

# Correlation ID shared by tool calls in the current execution context.
_workflow_id = contextvars.ContextVar("workflow_id", default=None)

# In-process counters; reset when the server process restarts.
_metrics = Counter()


def get_workflow_id() -> str | None:
    """Return the active workflow correlation ID, if available."""
    return _workflow_id.get()


def start_workflow(workflow_id: str | None = None) -> str:
    """Set a workflow ID for the current execution context."""
    value = workflow_id or str(uuid.uuid4())
    _workflow_id.set(value)
    logger.info("workflow_started workflow_id=%s", value)
    return value


def end_workflow() -> None:
    """Log completion and clear the workflow ID."""
    value = _workflow_id.get()
    if value:
        logger.info("workflow_finished workflow_id=%s", value)
    _workflow_id.set(None)


def get_metrics() -> dict[str, int]:
    """Return a snapshot of in-process tool metrics."""
    return dict(_metrics)


def observed(tool_name: str | None = None):
    """Log tool outcome, duration and correlation ID without argument values."""
    def decorate(func: Callable[..., Any]):
        name = tool_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            workflow_id = _workflow_id.get() or "unassigned"

            try:
                result = func(*args, **kwargs)
                failed_result = (
                    isinstance(result, dict) and "error" in result
                )
                outcome = "error" if failed_result else "success"
                _metrics[f"{name}.{outcome}"] += 1

                logger.info(
                    "tool_call name=%s outcome=%s duration_ms=%.2f "
                    "workflow_id=%s",
                    name,
                    outcome,
                    (time.perf_counter() - started) * 1000,
                    workflow_id,
                )
                return result

            except Exception as exc:
                _metrics[f"{name}.exception"] += 1
                logger.exception(
                    "tool_call name=%s outcome=exception duration_ms=%.2f "
                    "workflow_id=%s error_type=%s",
                    name,
                    (time.perf_counter() - started) * 1000,
                    workflow_id,
                    type(exc).__name__,
                )
                raise

        return wrapper
    return decorate
