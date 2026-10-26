"""Fixtures. Database tests need PostgreSQL: PMD_TEST_DATABASE_URL (a database the tests may wipe)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PMD_TODAY", "2026-10-26")
os.environ.setdefault("PMD_PSEUDONYM_KEY", "test-pseudonym-key")


def _clear_caches() -> None:
    from pmd import config, db

    db.engine.cache_clear()
    for f in (config.settings, config.funds, config.vocabulary, config.contract):
        f.cache_clear()


def reset_database() -> None:
    from sqlalchemy import text

    from pmd import db

    with db.begin() as c:
        for s in ("raw", "pii", "ops", "serving", "pmd_util"):
            c.exec_driver_sql(f"drop schema if exists {s} cascade")
        for (s,) in c.execute(
            text("select schema_name from information_schema.schemata where schema_name like 'build\\_%'")
        ):
            c.exec_driver_sql(f"drop schema {s} cascade")


@pytest.fixture(scope="session")
def database() -> str:
    url = os.environ.get("PMD_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PMD_TEST_DATABASE_URL is not set")
    os.environ["PMD_DATABASE_URL"] = url
    _clear_caches()
    return url


@pytest.fixture(scope="session")
def world(database: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """A small simulated world, loaded, built, audited and published once for the whole session."""
    from pmd.flow import run
    from pmd_sim.build import build

    data = tmp_path_factory.mktemp("data")
    os.environ["PMD_DATA"] = str(data)
    build(ROOT, quick=True, data=data)
    reset_database()
    # the world reads payments from the topic's file; the Kafka test publishes and consumes on its own
    kafka = os.environ.pop("PMD_KAFKA_BOOTSTRAP", None)
    try:
        result = run("test_first")
    finally:
        if kafka:
            os.environ["PMD_KAFKA_BOOTSTRAP"] = kafka
    yield {"data": data, "run": result}
    os.environ.pop("PMD_DATA", None)
