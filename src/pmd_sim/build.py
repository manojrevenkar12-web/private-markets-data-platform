"""pmd-sim: writes three feeder funds, their target funds and their clients the way the sources hand them over.

pmd-sim [--root .] [--seed 2026] [--quick]
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from .world import build_world
from .writers import write_all

TODAY = dt.date(2026, 10, 26)


def today() -> dt.date:
    return dt.date.fromisoformat(os.environ["PMD_TODAY"]) if os.environ.get("PMD_TODAY") else TODAY


def build(root: Path, seed: int = 2026, quick: bool = False) -> dict[str, Any]:
    funds = yaml.safe_load((root / "config" / "funds.yaml").read_text(encoding="utf-8"))
    for sub in ("landing", "truth"):
        shutil.rmtree(root / "data" / sub, ignore_errors=True)
    world = build_world(funds, today(), seed=seed, n_clients=110 if quick else 420)
    return write_all(world, root, seed)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="pmd-sim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--quick", action="store_true", help="fewer clients (tests)")
    args = ap.parse_args()
    counts = build(args.root.resolve(), args.seed, args.quick)
    print("built", ", ".join(f"{k}: {v}" for k, v in counts.items()))
