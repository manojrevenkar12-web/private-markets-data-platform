-- Each client's share of each feeder per quarter. The share is the client's commitment over the feeder's
-- total: every client pays the same percentage of commitment on every call.
with cm as (
  select client_key, feeder, sum(amount) as commitment, min(signed_on) as signed_on
  from {{ ref('stg_commitments') }}
  group by client_key, feeder
),
paid as (
  select m.client_key, e.feeder, m.booked_on, m.amount
  from {{ ref('int_receipt_matching') }} m
  join {{ ref('int_expected_payments') }} e using (expected_id)
  where not m.provisional
),
dist as (
  select cm.client_key, d.feeder, d.pay_date, round(cm.commitment * d.percent / 100, 2) as amount
  from {{ ref('stg_distributions') }} d
  join cm on cm.feeder = d.feeder and cm.signed_on <= d.pay_date
)
select
  cm.client_key,
  cm.feeder,
  q.quarter_end,
  cm.commitment,
  round(cm.commitment / q.total_commitment, 8) as share,
  round(q.nav_eur * cm.commitment / q.total_commitment, 2) as nav_eur,
  coalesce((select sum(amount) from paid p where p.client_key = cm.client_key and p.feeder = cm.feeder and p.booked_on <= q.quarter_end), 0) as paid_in_eur,
  coalesce((select sum(amount) from dist d where d.client_key = cm.client_key and d.feeder = cm.feeder and d.pay_date <= q.quarter_end), 0) as distributed_eur,
  q.has_estimates as nav_has_estimates
from cm
join {{ ref('int_feeder_quarters') }} q on q.feeder = cm.feeder and q.quarter_end >= cm.signed_on
