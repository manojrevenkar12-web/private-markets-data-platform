"""Airflow DAG for the platform, generated from pmd.flow.TASKS so the scheduler and `pmd run` share one graph.

Each task calls `pmd.flow.run_task(name, run_id)` with Airflow's run id, so every task of a run works on the
same build schema. The build is audited before it is published; a blocked build fails the publish task and
leaves the serving views on the last good build.
"""

from __future__ import annotations

import pendulum
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

from pmd.flow import TASKS


def _run(name: str, run_id: str) -> None:
    from pmd.flow import run_task

    result = run_task(name, run_id)
    if name == "publish" and not (result or {}).get("published"):
        raise RuntimeError(f"not published: {result}")


with DAG(
    dag_id="private_markets",
    description="Load the day's sources, build into a schema of its own, audit it, publish it",
    schedule="15 6 * * 1-5",  # after the custodian's statements arrive, business days
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Berlin"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=5)},
    tags=["private-markets"],
) as dag:
    ops = {
        t.name: PythonOperator(
            task_id=t.name,
            python_callable=_run,
            op_kwargs={"name": t.name, "run_id": "{{ run_id }}"},
            doc_md=t.doc,
        )
        for t in TASKS
    }
    for t in TASKS:
        for up in t.upstream:
            ops[up] >> ops[t.name]
