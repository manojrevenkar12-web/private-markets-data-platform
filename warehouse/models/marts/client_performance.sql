-- Since-inception performance per client and feeder at the latest quarter end: what went in, what came out,
-- what is left, and the money-weighted return (XIRR) of those cash flows with the NAV as the last one.
with pos as (
  select p.*
  from {{ ref('fct_client_positions') }} p
  join (select feeder, max(quarter_end) as quarter_end from {{ ref('fct_client_positions') }} group by feeder) l
    using (feeder, quarter_end)
),
flows as (
  select m.client_key, e.feeder, m.booked_on as d, -m.amount as amount
  from {{ ref('int_receipt_matching') }} m
  join {{ ref('int_expected_payments') }} e using (expected_id)
  where not m.provisional
  union all
  select cm.client_key, d.feeder, d.pay_date, round(cm.amount * d.percent / 100, 2)
  from {{ ref('stg_distributions') }} d
  join (select client_key, feeder, sum(amount) as amount, min(signed_on) as signed_on
        from {{ ref('stg_commitments') }} group by client_key, feeder) cm
    on cm.feeder = d.feeder and cm.signed_on <= d.pay_date
)
select
  pos.client_key,
  pos.feeder,
  pos.quarter_end as as_of_quarter,
  pos.commitment,
  pos.paid_in_eur,
  pos.distributed_eur,
  pos.nav_eur,
  pos.commitment - pos.paid_in_eur as unfunded_eur,
  case when pos.paid_in_eur > 0 then round(pos.distributed_eur / pos.paid_in_eur, 4) end as dpi,
  case when pos.paid_in_eur > 0 then round((pos.distributed_eur + pos.nav_eur) / pos.paid_in_eur, 4) end as tvpi,
  pmd_util.xirr(
    array_append(array_agg(f.d order by f.d), pos.quarter_end),
    array_append(array_agg(f.amount order by f.d), pos.nav_eur)
  ) as irr,
  pos.nav_has_estimates
from pos
left join flows f on f.client_key = pos.client_key and f.feeder = pos.feeder and f.d <= pos.quarter_end
group by pos.client_key, pos.feeder, pos.quarter_end, pos.commitment, pos.paid_in_eur, pos.distributed_eur,
         pos.nav_eur, pos.nav_has_estimates
