"""Publishes the simulated payment notifications to Kafka, keyed by account (one account, one partition order).

python -m pmd_sim.publish --bootstrap localhost:9092 [--root .]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def publish(bootstrap: str, root: Path, topic: str = "payments.received", partitions: int = 3) -> int:
    from confluent_kafka import Producer
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    if topic not in admin.list_topics(timeout=10).topics:
        for f in admin.create_topics([NewTopic(topic, num_partitions=partitions, replication_factor=1)]).values():
            f.result()
    p = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True})
    n = 0
    for line in (root / "data" / "landing" / "events" / "payments.jsonl").read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        p.produce(topic, key=ev["account_iban"].encode(), value=line.encode())
        n += 1
    p.flush(30)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args()
    print("published", publish(args.bootstrap, args.root.resolve()), "events")


if __name__ == "__main__":
    main()
