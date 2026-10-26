-- Quarters a manager reported again with different numbers, and by how much.
select
  fund, period_end, version, file_id, received_on, previous_version_nav, nav,
  nav - previous_version_nav as change_ccy,
  round((nav - previous_version_nav) / nullif(previous_version_nav, 0), 4) as change_share,
  currency
from {{ ref('int_statement_versions') }}
where version > 1 and nav <> previous_version_nav
