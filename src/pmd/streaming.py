"""The payments topic: instant notifications of money arriving on the feeder accounts, hours before the bank's
end-of-day statement. Delivery is at least once and not in order, so the consumer:

- stores each event under its event id (a redelivery is a no-op),
- pseudonymises the payer before anything is written,
- commits its offset only after the database transaction that stored the batch,
- sends an event that breaks the contract (config/contracts/payment_event.yaml) to ops.dead_events with the
  rule, never back onto the topic.

With PMD_KAFKA_BOOTSTRAP set it reads Kafka (or Redpanda); without it, the same code reads the topic's file
copy in data/landing/events, keeping its offset in ops.consumer_offsets.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Connection

from . import db
from .config import feeder_accounts, landing_dir
from .privacy import counterparty_key, redact_remittance

TOPIC = "payments.received"
CONSUMER = "pmd-cash"


@dataclass
class Message:
    partition: int
    offset: int
    value: bytes


class Source(Protocol):
    def batches(self, size: int) -> Iterator[list[Message]]: ...
    def committed(self, c: Connection, batch: list[Message]) -> None: ...
    def close(self) -> None: ...


class FileSource:
    """The topic's file copy, one partition; the offset is the line number, stored with the data."""

    def __init__(self, path: Path):
        self.path = path

    def batches(self, size: int) -> Iterator[list[Message]]:
        start = (
            db.scalar(
                "select next_offset from ops.consumer_offsets where consumer = :c and topic = :t and part = 0",
                c=CONSUMER,
                t=TOPIC,
            )
            or 0
        )
        lines = self.path.read_bytes().splitlines() if self.path.exists() else []
        for i in range(start, len(lines), size):
            yield [Message(0, i + k, line) for k, line in enumerate(lines[i : i + size])]

    def committed(self, c: Connection, batch: list[Message]) -> None:
        c.execute(
            text(
                """insert into ops.consumer_offsets values (:c, :t, 0, :o)
                   on conflict (consumer, topic, part) do update set next_offset = excluded.next_offset"""
            ),
            {"c": CONSUMER, "t": TOPIC, "o": batch[-1].offset + 1},
        )

    def close(self) -> None:
        pass


class KafkaSource:  # pragma: no cover - exercised by tests marked kafka
    def __init__(self, bootstrap: str, idle_seconds: float = 3.0):
        from confluent_kafka import Consumer

        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": CONSUMER,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "isolation.level": "read_committed",
            }
        )
        self.consumer.subscribe([TOPIC])
        self.idle = idle_seconds

    def batches(self, size: int) -> Iterator[list[Message]]:
        while True:
            msgs = self.consumer.consume(num_messages=size, timeout=self.idle)
            msgs = [m for m in msgs if m.error() is None]
            if not msgs:
                return
            # an empty value (a tombstone) cannot be parsed and goes to the dead letters like any bad event
            yield [Message(m.partition() or 0, m.offset() or 0, m.value() or b"") for m in msgs]

    def committed(self, c: Connection, batch: list[Message]) -> None:
        pass  # Kafka offsets are committed after the database commit, in consume()

    def commit(self) -> None:
        self.consumer.commit(asynchronous=False)

    def close(self) -> None:
        self.consumer.close()


def source() -> Source:
    boot = os.environ.get("PMD_KAFKA_BOOTSTRAP")
    if boot:
        return KafkaSource(boot)
    return FileSource(landing_dir() / "events" / "payments.jsonl")


def _validate(ev: dict[str, Any], accounts: dict[str, str]) -> tuple[str, str] | None:
    for f in ("event_id", "type", "account_iban", "amount", "currency", "received_at"):
        if not ev.get(f):
            return "required_fields", f"missing {f}"
    if ev["type"] != "payment.received":
        return "type_known", ev["type"]
    if ev["currency"] != "EUR":
        return "currency_eur", ev["currency"]
    try:
        if Decimal(str(ev["amount"])) <= 0:
            return "amount_positive", str(ev["amount"])
    except InvalidOperation:
        return "amount_positive", "not a number"
    if ev["account_iban"] not in accounts:
        return "account_known", "not a feeder account"
    return None


def consume(src: Source | None = None, batch_size: int = 200) -> dict[str, int]:
    src = src or source()
    accounts = feeder_accounts()
    stats = {"messages": 0, "stored": 0, "redelivered": 0, "dead": 0}
    try:
        for batch in src.batches(batch_size):
            with db.begin() as c:
                for m in batch:
                    stats["messages"] += 1
                    try:
                        ev = json.loads(m.value)
                    except (ValueError, UnicodeDecodeError):
                        _dead(c, None, "not_json", "the message is not JSON", m)
                        stats["dead"] += 1
                        continue
                    broken = _validate(ev, accounts)
                    if broken:
                        _dead(c, ev.get("event_id"), *broken, m)
                        stats["dead"] += 1
                        continue
                    red, call, client = redact_remittance(ev.get("remittance", ""))
                    ck = counterparty_key(ev.get("debtor_iban") or "UNKNOWN")
                    res = c.execute(
                        text(
                            """insert into raw.payment_events (event_id, account_iban, amount, counterparty_key,
                               remittance, ref_call_id, ref_client_key, received_at, bank_ref, topic_partition, topic_offset)
                               values (:e, :a, :m, :ck, :r, :call, :cl, :t, :b, :p, :o)
                               on conflict (event_id) do nothing"""
                        ),
                        {
                            "e": ev["event_id"],
                            "a": ev["account_iban"],
                            "m": Decimal(str(ev["amount"])),
                            "ck": ck,
                            "r": red,
                            "call": call,
                            "cl": client,
                            "t": dt.datetime.fromisoformat(ev["received_at"]),
                            "b": ev.get("bank_ref"),
                            "p": m.partition,
                            "o": m.offset,
                        },
                    )
                    if res.rowcount:
                        stats["stored"] += 1
                        c.execute(
                            text("insert into pii.counterparty_vault values (:k, :n, :i) on conflict do nothing"),
                            {"k": ck, "n": ev.get("debtor_name"), "i": ev.get("debtor_iban")},
                        )
                    else:
                        stats["redelivered"] += 1
                src.committed(c, batch)
            if isinstance(src, KafkaSource):
                src.commit()
    finally:
        src.close()
    return stats


def _dead(c: Connection, event_id: str | None, rule: str, detail: str, m: Message) -> None:
    c.execute(
        text(
            "insert into ops.dead_events (event_id, rule, detail, topic_partition, topic_offset) values (:e, :r, :d, :p, :o)"
        ),
        {"e": event_id, "r": rule, "d": detail, "p": m.partition, "o": m.offset},
    )
