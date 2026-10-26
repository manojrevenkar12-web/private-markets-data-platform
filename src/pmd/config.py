"""Where things are and what the thresholds are. Everything tunable lives in config/, not in code."""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def root() -> Path:
    env = os.environ.get("PMD_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "platform.yaml").exists():
            return parent
    return Path.cwd()


def data_dir() -> Path:
    return Path(os.environ.get("PMD_DATA", root() / "data"))


def landing_dir() -> Path:
    return data_dir() / "landing"


def today() -> dt.date:
    """The business date the platform runs for. Fixed in tests and demos through PMD_TODAY."""
    env = os.environ.get("PMD_TODAY")
    return dt.date.fromisoformat(env) if env else dt.date.today()


def database_url() -> str:
    return os.environ.get("PMD_DATABASE_URL", "postgresql+psycopg://pmd:pmd@localhost:5432/pmd")


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def settings() -> dict[str, Any]:
    return _load(root() / "config" / "platform.yaml")


@lru_cache
def funds() -> dict[str, Any]:
    return _load(root() / "config" / "funds.yaml")


@lru_cache
def vocabulary() -> dict[str, Any]:
    return _load(root() / "config" / "vocabulary.yaml")


@lru_cache
def contract(name: str) -> dict[str, Any]:
    return _load(root() / "config" / "contracts" / f"{name}.yaml")


def target_funds() -> dict[str, dict[str, Any]]:
    """Every target fund with the feeder that holds it."""
    out = {}
    for fid, f in funds()["feeders"].items():
        for tid, t in f["targets"].items():
            out[tid] = {**t, "id": tid, "feeder": fid}
    return out


def feeder_accounts() -> dict[str, str]:
    """Collection account IBAN -> feeder."""
    return {f["collection_account"]: fid for fid, f in funds()["feeders"].items()}
