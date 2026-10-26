# What this was built against

The project answers a job advertisement for a Senior Data Engineer at LIQID in Berlin. This file records what
the advertisement and LIQID's own publications say, and how each point shaped the platform. Nothing here
claims knowledge of LIQID's internal systems; the firm in the platform (Northlake Wealth) is fictional.

## The role

The advertisement asks for scalable, secure and reliable pipelines and storage; ETL/ELT from many sources;
data quality, validation and monitoring; security and compliance for sensitive data; data models and
self-service BI with other teams; SQL and Python; BigQuery, Snowflake or PostgreSQL; AWS or Google Cloud;
Airflow and dbt; and interest in fintech.

| The advertisement asks for | Where it is in the platform |
| --- | --- |
| ETL/ELT from multiple sources | GP statements in five formats and two languages, camt.053, a Kafka payment feed, CRM and ops files, each with a contract in `config/contracts` |
| Data quality, validation, monitoring | contracts and quarantine at the door; statement checks that hold a statement; dbt tests in every build; gates before publishing; freshness per feed |
| Security and compliance for sensitive data | pseudonymisation at the door, a PII vault, a logged reveal behind a database role, GDPR erasure against the retention duties of GwG §8 and HGB §257 |
| Data models, self-service BI | dbt staging, intermediate and marts with documented columns; serving views that only ever show an audited build; an API and console on top |
| SQL, Python, PostgreSQL, Airflow, dbt | all of it; dbt-postgres, an Airflow 3 DAG generated from the same task graph as the CLI |
| Reliability | write-audit-publish with one-transaction switches, idempotent loads and consumer, advisory lock per run, data diff per build |

## The business

- LIQID is a Berlin wealth manager with about EUR 2.5 billion under management and more than 8,000 clients,
  over 2,500 of whom invest in its private markets offering ([press release, July 2023][pr]).
- Its private equity funds of funds pool affluent private investors into institutional funds (managers such
  as KKR, EQT, Permira and Bridgepoint are named); LIQID Private Equity IV closed at EUR 200 million, and a
  fifth generation followed. The offering also covers venture capital and real estate ([press release][pr],
  [LIQID][liqid]).

What follows from that for data: a feeder fund invests in a dozen target funds, each of which reports
quarterly by statement, in its own format, often late and sometimes restated; clients pay capital calls by
bank transfer and expect their NAV, IRR and look-through to be right. The hard data problems are therefore
reading statements reliably, never showing an estimate as a fact, reconciling money, and keeping personal
data out of the analytical layer. The platform is built around those four.

## Sources

[pr]: https://presseportal.de/pm/120397/5555088?langid=2
[liqid]: https://www.liqid.de/presse/german-wealthtech-firm-closes-pe-fund-of-funds-after-record-eu200m-raise

- [LIQID: Democratisation of Private Equity Gains Pace, LIQID Closes EUR200 Million Fund (presseportal)][pr]
- [LIQID press page on the EUR 200m fund of funds][liqid]
- [LIQID Senior Data Engineer advertisement (arbeitnow)](https://arbeitnow.com/jobs/companies/liqid-investments-gmbh/senior-data-engineer-berlin-43455)
