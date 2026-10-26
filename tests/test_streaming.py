from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from pmd import db
from pmd.streaming import FileSource, consume


def test_redelivered_events_are_stored_once(world: dict[str, Any]) -> None:
    events = db.scalar("select count(*) from raw.payment_events")
    lines = (world["data"] / "landing" / "events" / "payments.jsonl").read_text().splitlines()
    ids = {json.loads(x)["event_id"] for x in lines}
    assert events == len(ids) < len(lines)
    assert consume()["messages"] == 0  # the offset is stored: nothing to read twice


def test_bad_events_go_to_dead_letters_and_good_ones_through(world: dict[str, Any], tmp_path: Path) -> None:
    topic = tmp_path / "topic.jsonl"
    good = json.loads((world["data"] / "landing" / "events" / "payments.jsonl").read_text().splitlines()[0])
    rows = [
        b"not json",
        json.dumps({**good, "event_id": "evt-test-eur", "currency": "USD"}).encode(),
        json.dumps({**good, "event_id": "evt-test-neg", "amount": "-5"}).encode(),
        json.dumps({**good, "event_id": "evt-test-acct", "account_iban": "DE00123"}).encode(),
        json.dumps({**good, "event_id": "evt-test-ok", "bank_ref": "X-NEW"}).encode(),
    ]
    topic.write_bytes(b"\n".join(rows))
    with db.begin() as c:
        c.exec_driver_sql("delete from ops.consumer_offsets")
    try:
        stats = consume(FileSource(topic))
        assert stats == {"messages": 5, "stored": 1, "redelivered": 0, "dead": 4}
        rules = {r["rule"] for r in db.rows("select rule from ops.dead_events")}
        assert {"not_json", "currency_eur", "amount_positive", "account_known"} <= rules
        assert db.scalar("select counterparty_key from raw.payment_events where event_id = 'evt-test-ok'").startswith(
            "cp_"
        )
    finally:
        with db.begin() as c:
            c.exec_driver_sql("delete from raw.payment_events where event_id like 'evt-test-%%'")
            c.exec_driver_sql("delete from ops.dead_events")
            c.exec_driver_sql(
                "update ops.consumer_offsets set next_offset = %(n)s",
                {"n": len((world["data"] / "landing" / "events" / "payments.jsonl").read_text().splitlines())},
            )


@pytest.mark.kafka
def test_kafka_end_to_end(world: dict[str, Any]) -> None:
    boot = os.environ.get("PMD_KAFKA_BOOTSTRAP")
    if not boot:
        pytest.skip("PMD_KAFKA_BOOTSTRAP is not set")
    from pmd.streaming import KafkaSource

    with db.begin() as c:
        c.exec_driver_sql("truncate raw.payment_events")
    lines = (world["data"] / "landing" / "events" / "payments.jsonl").read_text().splitlines()
    from confluent_kafka import Producer

    p = Producer({"bootstrap.servers": boot, "enable.idempotence": True})
    for line in lines:
        p.produce("payments.received", key=json.loads(line)["account_iban"].encode(), value=line.encode())
    p.flush(30)
    stats = consume(KafkaSource(boot, idle_seconds=5))
    ids = {json.loads(x)["event_id"] for x in lines}
    assert db.scalar("select count(*) from raw.payment_events") == len(ids)
    assert stats["stored"] == len(ids)
    # a second consumer in the same group finds nothing new: offsets were committed after the database
    assert consume(KafkaSource(boot, idle_seconds=3))["messages"] == 0
