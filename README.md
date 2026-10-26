# Private markets data platform

A data platform for a digital wealth manager that runs private equity, venture and private debt feeder funds
for private clients. It takes the sources such a firm actually lives on, the GP capital account statements
(PDF, Excel and CSV, in English and German), the custodian's camt.053 bank statements, an instant payment
feed on Kafka, a CRM export full of personal data and the operations team's own files, and turns them into
numbers a client may see: NAV per fund and per client, look-through to the target funds, IRR, TVPI, and the
status of every capital call.

The firm, its 420 clients, 3 feeder funds and 12 target funds are simulated (`pmd-sim`), with the problems
real sources have planted on purpose and the truth kept apart, so the platform can be measured against it.

![Today: the run ribbon, feeder NAVs, open capital calls and breaks](docs/screenshots/today.png)

## What it does

- **Reads GP statements by their labels, not their layout.** One parser for PDF, Excel, CSV, Markdown and
  text, in English and German, driven by a vocabulary in `config/vocabulary.yaml`: cumulative versus
  quarter-to-date figures, closing versus opening NAV, amounts in thousands or millions, German number
  formats. A statement it cannot read with confidence is quarantined with the reason, never guessed.
- **Keeps every version of every statement.** Statements are bitemporal (`known_from`, `known_until`), so a
  restated quarter replaces the old figure without erasing it, and the console can show any fund *as it was
  known on a given day*.
- **Holds a statement whose numbers do not add up.** A commitment that differs from the agreed one, a
  cumulative figure that falls, or a NAV move that the quarter's cash flows do not explain keeps the
  statement out of the numbers until fund accounting releases it; the quarter is estimated meanwhile.
- **Estimates honestly and says so.** A late or held quarter is carried forward from the last statement
  with the calls and distributions the bank has booked since, and every estimated figure is marked as one,
  in the marts, the API and on screen.
- **Reconciles money.** Capital call payments are matched to calls by reference (call and client), else by
  the payer's account; short, over, late, duplicate, unpaid and unplaceable payments become breaks with
  stable ids, so what operations did about a break survives the next run.
- **Never lets personal data into the warehouse.** Client ids become HMAC keys at the door, remittance text
  is redacted, names and IBANs live only in a vault. Seeing who a client is takes the operations role, a
  reason and a security-definer function that logs every attempt. Erasure requests delete a prospect and
  keep an investor for the statutory retention period (GwG §8, HGB §257). A database refuses to load with a
  different pseudonymisation key than the one it was built with.
- **Writes, audits, publishes.** Every run builds the dbt project into a schema of its own, runs the gates
  on it (dbt tests, empty marts, fund NAV drift without a new statement, unplaced money, overdue calls, late
  and held statements) and only then points the serving views at it, in one transaction. A blocked build
  stays for a person to look at; a build stopped only by the drift gate can be published by a second person
  (`pmd approve`). Each run records a mart-by-mart diff against what clients saw before.
- **Streams payments.** The instant payment consumer is idempotent by event id and commits Kafka offsets
  only after the database commit; events nobody can apply go to dead letters.
- **Runs the same graph in Airflow and on the command line.** The Airflow 3 DAG is generated from
  `pmd.flow.TASKS`, which `pmd run` also executes.

## Measured

On the simulated firm (seed 2026, business date 2026-10-26; `pmd evaluate` compares with the truth that only
`src/pmd/evaluate.py` may read):

| | |
| --- | --- |
| GP statements read right, every field | 103 of 103 |
| Planted problems found (restatement, duplicate file, unlabelled thousands, scan, late statement, 432 payment problems, two erasures) | 439 of 439 |
| Breaks the truth does not explain | 0 |
| Quarters with a statement, NAV right | 103 of 103 |
| Quarters estimated, median error against the truth | 14, 2.3 % |
| One run: load, dbt build (33 models over 20 sources, with their tests), gates, publish | about 30 s |

The simulator and the parser were written by the same hand, so those numbers say the pipeline works, not
that the parser reads any manager's statement. The held-out sets measure that. Each was written by an agent
that had read only `heldout/WRITING_STATEMENTS.md` and never saw the code; the first run is recorded once and
never rewritten (CI checks it).

| Held-out set | Read right (accept) | Rejected as expected | Status |
| --- | --- | --- | --- |
| v1, 30 statements | 2 of 25 | 5 of 5 | studied; the parser was reworked on it, now a regression set (25 of 25, not a measure) |
| v2, 30 statements | 14 of 25 | 4 of 5 | first run with the parser frozen |

In v2, 9 of the 11 misses were rejected to quarantine (the safe failure: a person reads them), 2 were
accepted with one wrong figure, and 1 statement for a fund not in the fund list was accepted when it should
have been rejected. Paid-in is the weakest field (18 of 25). The case list was printed when the first run
was recorded but the parser has not been changed for it; the next parser change makes v2 a regression set
and needs a v3 written blind.

## Tests

- `pytest -q`: 57 tests on PostgreSQL (parsers, privacy, pipeline, API, isolation of the truth, the task
  graph), plus a Kafka end-to-end test that runs against Redpanda in CI and an Airflow test that loads the
  DAG in Airflow 3.3.2 (its own CI job; it passed locally in a separate environment).
- dbt tests inside every build: unique and not-null keys, value ranges, feeder NAV equals the sum of client
  positions, look-through equals the position, every receipt applied once, bank statement sequences and
  balances chain, no personal data in any mart, XIRR on known cash flows.
- `cd web && npm run check`: TypeScript, ESLint, Prettier and 38 Vitest tests on API answers captured from a
  real run; `npx playwright test`: 4 flows on desktop and phone against the running API.

## Run it

```sh
docker compose up        # PostgreSQL, Redpanda, one pipeline run, then http://localhost:8000
```

Or by hand, with PostgreSQL running:

```sh
pip install -e ".[dev]"
export PMD_DATABASE_URL=postgresql+psycopg://pmd:pmd@localhost:5432/pmd PMD_TODAY=2026-10-26
pmd-sim                  # the simulated sources in data/landing, the truth in data/truth
pmd run                  # load, build, audit, publish
pmd evaluate             # against the truth
pmd heldout v2           # a held-out set (first run already recorded)
pmd serve                # API and console on :8000 (cd web && npm ci && npm run build first)
```

`PMD_KAFKA_BOOTSTRAP` switches the payment consumer from the topic's file to Kafka; `PMD_API_TOKENS`
(`token:actor:role,...`) switches the API from development headers to bearer tokens;
`PMD_PSEUDONYM_KEY` is the pseudonymisation secret.

## The console

React 19 with TanStack Query and Framer Motion, in feature folders (`web/src/features`) over shared design
tokens. Every view has a skeleton, an error with a retry, and an empty state that says what to do.

- **Today**: the run ribbon (every build as a column of gates, the one clients see marked), feeder NAVs,
  open capital calls split into booked, arrived-but-not-booked and outstanding, open breaks, source freshness.
- **Breaks**: the reconciliation queue by owner, kind and status; operations and fund accounting resolve,
  reopen and annotate.
- **Funds**: NAV per quarter with estimates hatched and restated quarters outlined, the switch to *as known
  on* any day, every statement version, held statements with their release.
- **Clients**: by key only; performance, look-through, payments, breaks, and the logged reveal.
- **Data health**, **Runs** (gates and diff), **Lineage** (from dbt's manifest).

| | |
| --- | --- |
| ![KES4 as known before its restatement](docs/screenshots/fund-as-known.png) | ![Acting on a break](docs/screenshots/break-action.png) |

## Where things are

```
src/pmd_sim/      the simulated firm and its truth
src/pmd/          landing, parsers, loaders, streaming, warehouse (dbt runner), publish, flow, API, evaluate
warehouse/        dbt project: staging, intermediate, marts, tests, macros (XIRR in PL/pgSQL)
config/           thresholds, funds, vocabulary, data contracts: settings never live in code
dags/             Airflow 3 DAG generated from pmd.flow.TASKS
heldout/          blind statement sets, their answers and the guide they were written from
web/              the console
docs/             research, design, decisions
```

See [docs/DESIGN.md](docs/DESIGN.md) for how it fits together and why, [docs/adr](docs/adr) for the
decisions, and [docs/RESEARCH.md](docs/RESEARCH.md) for what it was built against.

## Limits

Simulated sources only; no real manager's statement has been through it. The parser has no OCR (a scan is
quarantined and the manager asked for the original). FX is one EUR/USD rate per day. Estimates use booked
cash flows only, no market proxy. It runs on PostgreSQL; the dbt models are plain SQL apart from the
PL/pgSQL XIRR and would need that ported for BigQuery or Snowflake.
