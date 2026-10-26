"""Boundaries that must hold: the platform never sees the simulator or its truth, and dbt never reads pii."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_platform_never_imports_the_simulator() -> None:
    for path in (ROOT / "src" / "pmd").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(n.startswith("pmd_sim") for n in names), path


def test_only_evaluate_reads_the_truth() -> None:
    for path in (ROOT / "src" / "pmd").rglob("*.py"):
        if path.name in ("evaluate.py",):
            continue
        assert '"truth"' not in path.read_text(encoding="utf-8"), path


def test_dbt_models_never_read_personal_data() -> None:
    for path in (ROOT / "warehouse").rglob("*.sql"):
        text = path.read_text(encoding="utf-8").lower()
        assert not re.search(r"\bpii\.", text), path
        assert "source('pii'" not in text, path


def test_thresholds_live_in_config() -> None:
    gates = (ROOT / "src" / "pmd" / "publish.py").read_text(encoding="utf-8")
    assert "0.25" not in gates and "0.40" not in gates
    project = (ROOT / "warehouse" / "dbt_project.yml").read_text(encoding="utf-8")
    assert "Overridden on every run by pmd from config/platform.yaml" in project
