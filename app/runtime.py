"""The runtimes behind the api and the worker, built lazily per agent, and the
dispatcher between them.

Both services import this module. The api builds the runtime of each agent it
serves on first use (so it boots without Mongo, BigQuery or Vertex AI reachable);
the worker builds the one agent it runs. Tests swap runtimes and the dispatcher in
with ``set_runtime`` / ``set_dispatcher``.
"""

from __future__ import annotations

from typing import Any

from factory import AGENT_ORDER_INTAKE, AGENT_PREBILL, settings
from factory.dispatch import Dispatcher, InlineDispatcher, PubSubDispatcher, WorkItem
from factory.intake import Poller, RawCase

SLUGS: dict[str, str] = {"order-intake": AGENT_ORDER_INTAKE, "prebill": AGENT_PREBILL}
EVENT_KINDS: dict[str, str] = {AGENT_ORDER_INTAKE: "cases", AGENT_PREBILL: "invoices"}

_runtimes: dict[str, Any] = {}
_sweepers: dict[str, Poller] = {}
_dispatcher: Dispatcher | None = None


def agent_for(slug: str) -> str:
    try:
        return SLUGS[slug]
    except KeyError:
        raise RuntimeError(f"unknown agent {slug!r}; INGREDION_AGENTS takes {sorted(SLUGS)}") from None


def _build(agent: str) -> Any:
    if agent == AGENT_ORDER_INTAKE:
        from order_intake_agent.runtime import build_runtime

        return build_runtime()
    if agent == AGENT_PREBILL:
        from prebill_agent.runtime import build_runtime

        return build_runtime()
    raise RuntimeError(f"unknown agent {agent!r}")


def get_runtime(agent: str) -> Any:
    rt = _runtimes.get(agent)
    if rt is None:
        rt = _runtimes[agent] = _build(agent)
    return rt


def set_runtime(agent: str, runtime: Any) -> None:
    """Replace one agent's runtime (tests). ``None`` rebuilds from the environment on next use."""
    if runtime is None:
        _runtimes.pop(agent, None)
    else:
        _runtimes[agent] = runtime
    _sweepers.pop(agent, None)


def _run_inline(agent: str) -> Any:
    def handler(raw: RawCase) -> Any:
        return get_runtime(agent).pipeline.process_raw(raw)

    return handler


def get_dispatcher() -> Dispatcher:
    """Pub/Sub when a work topic is configured for any agent, inline (Dev) otherwise."""
    global _dispatcher
    if _dispatcher is None:
        topics = {agent: topic for agent in SLUGS.values() if (topic := settings.work_topic(agent))}
        if topics:
            project, _ = settings.gcp()
            if not project:
                raise RuntimeError("WORK_TOPIC_* is set but GOOGLE_CLOUD_PROJECT is not")
            _dispatcher = PubSubDispatcher(project, topics)
        else:
            _dispatcher = InlineDispatcher({agent: _run_inline(agent) for agent in SLUGS.values()})
    return _dispatcher


def set_dispatcher(dispatcher: Dispatcher | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher
    _sweepers.clear()


def get_sweeper(agent: str) -> Poller:
    """A poller over the agent's intake source whose hand-off is the dispatcher: one
    pass claims and dispatches anything the change signal missed."""
    poller = _sweepers.get(agent)
    if poller is None:
        rt = get_runtime(agent)
        poller = _sweepers[agent] = Poller(
            rt.source,
            rt.ctx.claims,
            lambda raw, a=agent: get_dispatcher().submit(WorkItem.from_raw(a, raw, origin="sweep")),
            kill_switch=rt.ctx.kill_switch,
            owner=f"{agent}:sweep",
        )
    return poller


def reset() -> None:
    """Forget every runtime, sweeper and the dispatcher (tests)."""
    _runtimes.clear()
    _sweepers.clear()
    set_dispatcher(None)


__all__ = ["EVENT_KINDS", "SLUGS", "agent_for", "get_dispatcher", "get_runtime", "get_sweeper", "reset", "set_dispatcher", "set_runtime"]
