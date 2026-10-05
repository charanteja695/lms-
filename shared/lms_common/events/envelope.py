"""Shape of every message on the ``lms:events`` Redis Stream (see lms-backend/README.md §5).

A publishing service writes ``event_type``, ``aggregate_type``, ``occurred_time`` and a
``payload`` of public ids only, in the same transaction as the change (transactional outbox).
Delivery is at-least-once: consumers must de-duplicate on ``event_id``.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    event_type: str
    aggregate_type: str
    occurred_time: datetime
    payload: dict[str, object]

    @classmethod
    def from_stream_fields(cls, fields: dict[str, str]) -> "Event":
        import json

        return cls(
            event_id=fields["event_id"],
            event_type=fields["event_type"],
            aggregate_type=fields["aggregate_type"],
            occurred_time=datetime.strptime(fields["occurred_time"], "%Y-%m-%dT%H:%M:%SZ"),
            payload=json.loads(fields["payload"]),
        )
