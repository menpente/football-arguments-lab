"""Optional Opik tracing for the pipeline.

Opt-in: tracing is active only when the ``OPIK_TRACING`` env var is truthy
AND the ``opik`` package is importable
(``pip install -r requirements-tracing.txt``). Otherwise everything here is
a zero-cost no-op and ``opik`` is never imported, so the pipeline keeps
running fully offline with no dependency beyond Jinja2.

Endpoint / auth / workspace come from Opik's own env vars
(``OPIK_API_KEY``, ``OPIK_URL_OVERRIDE``, ``OPIK_WORKSPACE``,
``OPIK_PROJECT_NAME``) — works against Opik Cloud or a self-hosted
instance with no code change. Only the project name is defaulted.
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable, TypeVar

_TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_PROJECT = "football-editorial-agent"

F = TypeVar("F", bound=Callable[..., Any])

_enabled: bool | None = None
_opik: Any = None


def tracing_enabled() -> bool:
    """True iff OPIK_TRACING is set and `opik` imports. Cached after first call."""
    global _enabled, _opik
    if _enabled is None:
        _enabled = False
        if os.environ.get("OPIK_TRACING", "").strip().lower() in _TRUTHY:
            try:
                import opik  # noqa: PLC0415

                _opik = opik
                os.environ.setdefault("OPIK_PROJECT_NAME", DEFAULT_PROJECT)
                _enabled = True
            except Exception:
                _enabled = False
    return _enabled


def traced(name: str | None = None, span_type: str = "general") -> Callable[[F], F]:
    """Record the decorated call as an Opik span when tracing is enabled.

    When disabled the decorator returns the function unchanged (no wrapper
    cost, no import of opik).
    """

    def decorator(func: F) -> F:
        cache: dict[str, Callable[..., Any]] = {}

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not tracing_enabled():
                return func(*args, **kwargs)
            tracked = cache.get("fn")
            if tracked is None:
                tracked = _opik.track(name=name or func.__name__, type=span_type)(func)
                cache["fn"] = tracked
            return tracked(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def annotate(**metadata: Any) -> None:
    """Attach metadata to the current span. No-op when tracing is disabled."""
    if not tracing_enabled():
        return
    try:
        from opik import opik_context  # noqa: PLC0415

        opik_context.update_current_span(metadata=metadata)
    except Exception:
        pass


def flush() -> None:
    """Flush buffered traces to the backend. No-op when tracing is disabled."""
    if not tracing_enabled():
        return
    for attempt in (lambda: _opik.flush_tracker(), lambda: _opik.Opik().flush()):
        try:
            attempt()
            return
        except Exception:
            continue
