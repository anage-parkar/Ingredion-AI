"""Between the api and the worker.

The api service accepts an event (a Pub/Sub push from the data platform), claims
the case once and hands the run to the worker through a work topic; the worker
pulls, runs the pipeline and acknowledges. In Dev the ``InlineDispatcher`` runs the
pipeline in the request instead, so a laptop needs neither Pub/Sub nor a second
process. Both sides speak :class:`WorkItem`.
"""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .case import now_iso
from .intake import RawCase


@dataclass
class WorkItem:
    agent: str
    source_ref: str
    payload: dict[str, Any]
    marker: Any = None
    message_id: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    accepted_at: str = field(default_factory=now_iso)

    def to_raw(self) -> RawCase:
        return RawCase(source_ref=self.source_ref, marker=self.marker, payload=dict(self.payload))

    @classmethod
    def from_raw(cls, agent: str, raw: RawCase, **attributes: str) -> WorkItem:
        return cls(agent=agent, source_ref=raw.source_ref, payload=dict(raw.payload), marker=raw.marker, attributes=dict(attributes))

    def to_json(self) -> bytes:
        return json.dumps(asdict(self), default=str).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes | str) -> WorkItem:
        body = json.loads(data)
        return cls(
            agent=body["agent"],
            source_ref=body["source_ref"],
            payload=dict(body.get("payload") or {}),
            marker=body.get("marker"),
            message_id=body.get("message_id"),
            attributes=dict(body.get("attributes") or {}),
            accepted_at=body.get("accepted_at") or now_iso(),
        )


class Dispatcher(Protocol):
    name: str

    def submit(self, item: WorkItem) -> str:
        """Hand the item to the worker; returns a delivery id."""
        ...


class InlineDispatcher:
    """Runs the pipeline in the calling process (Dev, tests). Synchronous on purpose:
    the caller sees the exception and can release the claim."""

    name = "inline"

    def __init__(self, handlers: dict[str, Callable[[RawCase], Any]]) -> None:
        self.handlers = dict(handlers)
        self.submitted: list[WorkItem] = []

    def submit(self, item: WorkItem) -> str:
        handler = self.handlers.get(item.agent)
        if handler is None:
            raise LookupError(f"no handler for agent {item.agent!r}")
        self.submitted.append(item)
        handler(item.to_raw())
        return f"inline:{len(self.submitted)}"


class PubSubDispatcher:
    """Publishes the item to the agent's work topic; the worker pulls it."""

    name = "pubsub"

    def __init__(self, project: str, topics: dict[str, str], *, client: Any = None, timeout: float = 30.0) -> None:
        if not project:
            raise ValueError("PubSubDispatcher needs a project")
        self.project = project
        self.topics = dict(topics)
        self.timeout = timeout
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import pubsub_v1

            self._client = pubsub_v1.PublisherClient()
        return self._client

    def topic_path(self, agent: str) -> str:
        topic = self.topics.get(agent)
        if not topic:
            raise LookupError(f"no work topic configured for agent {agent!r}")
        return topic if topic.startswith("projects/") else f"projects/{self.project}/topics/{topic}"

    def submit(self, item: WorkItem) -> str:
        future = self._get_client().publish(self.topic_path(item.agent), item.to_json(), agent=item.agent, source_ref=item.source_ref)
        return str(future.result(timeout=self.timeout))


# ── the worker's side ────────────────────────────────────────────────────────


@dataclass
class Delivery:
    item: WorkItem
    ack_id: str
    attempt: int = 1


class WorkQueue(Protocol):
    name: str

    def pull(self, max_messages: int, timeout: float) -> list[Delivery]: ...

    def ack(self, delivery: Delivery) -> None: ...

    def nack(self, delivery: Delivery, *, delay_seconds: int = 0) -> None: ...

    def extend(self, delivery: Delivery, seconds: int) -> None: ...


class InMemoryWorkQueue:
    name = "memory"

    def __init__(self, items: list[WorkItem] | None = None) -> None:
        self._queue: deque[tuple[WorkItem, int]] = deque((i, 1) for i in (items or []))
        self.in_flight: dict[str, Delivery] = {}
        self.acked: list[Delivery] = []
        self.nacked: list[tuple[Delivery, int]] = []
        self.extended: list[tuple[str, int]] = []
        self._seq = 0

    def put(self, item: WorkItem) -> None:
        self._queue.append((item, 1))

    def __len__(self) -> int:
        return len(self._queue)

    def pull(self, max_messages: int, timeout: float = 0.0) -> list[Delivery]:
        out: list[Delivery] = []
        while self._queue and len(out) < max_messages:
            item, attempt = self._queue.popleft()
            self._seq += 1
            delivery = Delivery(item=item, ack_id=f"ack-{self._seq}", attempt=attempt)
            self.in_flight[delivery.ack_id] = delivery
            out.append(delivery)
        return out

    def ack(self, delivery: Delivery) -> None:
        self.in_flight.pop(delivery.ack_id, None)
        self.acked.append(delivery)

    def nack(self, delivery: Delivery, *, delay_seconds: int = 0) -> None:
        self.in_flight.pop(delivery.ack_id, None)
        self.nacked.append((delivery, delay_seconds))
        self._queue.append((delivery.item, delivery.attempt + 1))

    def extend(self, delivery: Delivery, seconds: int) -> None:
        self.extended.append((delivery.ack_id, seconds))


class PubSubWorkQueue:
    """Synchronous pull from the agent's work subscription. ``nack`` sets the ack
    deadline to zero so Pub/Sub redelivers (after the subscription's retry policy);
    ``extend`` keeps a long case leased. Poison messages end in the subscription's
    dead-letter topic, configured in Terraform, not here."""

    name = "pubsub"

    def __init__(self, project: str, subscription: str, *, client: Any = None) -> None:
        if not project or not subscription:
            raise ValueError("PubSubWorkQueue needs a project and a subscription")
        self.project = project
        self.subscription = subscription if subscription.startswith("projects/") else f"projects/{project}/subscriptions/{subscription}"
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import pubsub_v1

            self._client = pubsub_v1.SubscriberClient()
        return self._client

    def pull(self, max_messages: int, timeout: float) -> list[Delivery]:
        response = self._get_client().pull(request={"subscription": self.subscription, "max_messages": max_messages}, timeout=timeout)
        out: list[Delivery] = []
        for received in getattr(response, "received_messages", None) or []:
            message = received.message
            item = WorkItem.from_json(message.data)
            item.message_id = item.message_id or getattr(message, "message_id", None)
            out.append(Delivery(item=item, ack_id=received.ack_id, attempt=int(getattr(received, "delivery_attempt", 0) or 1)))
        return out

    def ack(self, delivery: Delivery) -> None:
        self._get_client().acknowledge(request={"subscription": self.subscription, "ack_ids": [delivery.ack_id]})

    def nack(self, delivery: Delivery, *, delay_seconds: int = 0) -> None:
        # Pub/Sub has no delayed nack; the subscription's retry policy spaces redeliveries.
        self._get_client().modify_ack_deadline(request={"subscription": self.subscription, "ack_ids": [delivery.ack_id], "ack_deadline_seconds": 0})

    def extend(self, delivery: Delivery, seconds: int) -> None:
        self._get_client().modify_ack_deadline(request={"subscription": self.subscription, "ack_ids": [delivery.ack_id], "ack_deadline_seconds": int(seconds)})


def drain(queue: WorkQueue, handler: Callable[[Delivery], None], *, max_messages: int = 10, timeout: float = 0.0, deadline: float | None = None) -> int:
    """Pull until the queue answers empty (or the deadline passes); returns the count handled."""
    handled = 0
    started = time.monotonic()
    while True:
        deliveries = queue.pull(max_messages, timeout)
        if not deliveries:
            return handled
        for delivery in deliveries:
            handler(delivery)
            handled += 1
        if deadline is not None and time.monotonic() - started > deadline:
            return handled


__all__ = [
    "Delivery",
    "Dispatcher",
    "InMemoryWorkQueue",
    "InlineDispatcher",
    "PubSubDispatcher",
    "PubSubWorkQueue",
    "WorkItem",
    "WorkQueue",
    "drain",
]
