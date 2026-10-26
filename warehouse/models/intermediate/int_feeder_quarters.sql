-- A feeder's NAV per quarter: its share of every target fund plus the cash on its account.
with quarters as (
  select distinct feeder, quarter_end from {{ ref('int_fund_quarters') }}
),
targets as (
  select feeder, quarter_end, sum(nav_eur) as targets_nav_eur,
         bool_or(nav_source = 'estimated') as has_estimates
  from {{ ref('int_fund_quarters') }}
  group by feeder, quarter_end
)
select
  q.feeder,
  q.quarter_end,
  t.targets_nav_eur,
  coalesce(cash.closing, 0) as cash_eur,
  t.targets_nav_eur + coalesce(cash.closing, 0) as nav_eur,
  t.has_estimates,
  (select sum(amount) from {{ ref('stg_commitments') }} c where c.feeder = q.feeder and c.signed_on <= q.quarter_end) as total_commitment
from quarters q
join targets t using (feeder, quarter_end)
left join lateral (
  select closing from {{ ref('stg_bank_statements') }} b
  where b.feeder = q.feeder and b.statement_date <= q.quarter_end
  order by b.statement_date desc, b.sequence desc limit 1
) cash on true
