from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pmd.flow import TASKS, order

ROOT = Path(__file__).resolve().parents[1]


def test_task_graph_is_ordered_and_ends_in_publish() -> None:
    names = [t.name for t in order()]
    assert names[0] == "bootstrap" and names[-1] == "cleanup"
    assert names.index("build") > max(names.index(n) for n in names if n.startswith(("load_", "consume_")))
    assert names.index("gates") < names.index("publish")


def test_airflow_dag_is_generated_from_the_same_graph() -> None:
    src = (ROOT / "dags" / "private_markets.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert any(isinstance(n, ast.ImportFrom) and n.module == "pmd.flow" for n in ast.walk(tree))


@pytest.mark.airflow
def test_airflow_loads_the_dag() -> None:
    pytest.importorskip("airflow")
    from airflow.models.dagbag import DagBag

    bag = DagBag(dag_folder=str(ROOT / "dags"), include_examples=False)
    assert not bag.import_errors, bag.import_errors
    dag = bag.get_dag("private_markets")
    assert {t.task_id for t in dag.tasks} == {t.name for t in TASKS}
    for t in TASKS:
        assert {u.task_id for u in dag.get_task(t.name).upstream_list} == set(t.upstream)
