# Working on this repository

## Fast feedback

- `pytest -q` (needs PostgreSQL: `PMD_TEST_DATABASE_URL`, a database the tests may reset). About a minute.
- `ruff check src tests dags && ruff format --check src tests dags && mypy src`.
- `cd web && npm run check` (types, lint, format, Vitest); `npx playwright test` against `pmd serve`.
- `pmd-sim && pmd run && pmd evaluate` with `PMD_TODAY=2026-10-26` for the whole pipeline against the truth.

## Invariants (each has a test or a gate)

- Only `src/pmd/evaluate.py` reads `data/truth`; nothing in `src/pmd` imports `pmd_sim`
  (`tests/test_isolation.py`).
- Personal data never reaches raw tables other than the vault, any build schema or the API: client ids are
  keyed at the door (`dbt test no_personal_data_in_marts`, `tests/test_privacy.py`).
- Serving views only ever point at a build whose blocking gates passed (`tests/test_pipeline.py`).
- An estimated figure is always marked as one, in marts, API and console.
- Statement versions are never updated or deleted; a restatement is a new version.
- Thresholds, vocabulary, contracts and funds live in `config/`, not in code.
- A new raw source comes with a contract in `config/contracts/`.

## Held-out statements

Never change the parser or the vocabulary to pass a held-out set before its first run is recorded
(`reports/heldout/<set>/first_run.json`, never rewritten; CI checks it). If you study a set's failures to
change the parser, write `regression` to `heldout/<set>/STATUS` and have someone who has not seen the code
write a new set from `heldout/WRITING_STATEMENTS.md` only.

## Where settings live

`config/platform.yaml` (gates, freshness, reconciliation, privacy, publish), `config/funds.yaml`,
`config/vocabulary.yaml`, `config/contracts/*.yaml`. Environment: `PMD_DATABASE_URL`, `PMD_TODAY`,
`PMD_PSEUDONYM_KEY`, `PMD_KAFKA_BOOTSTRAP`, `PMD_API_TOKENS`, `PMD_DATA`, `PMD_ROOT`.
