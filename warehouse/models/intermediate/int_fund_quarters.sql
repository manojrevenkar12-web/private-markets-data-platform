-- One row per target fund and quarter end, up to the last completed quarter. The NAV comes from the latest
-- statement version that passed its checks; where there is none (late, held) it is estimated from the last
-- statement plus the calls and minus the distributions the bank shows since, and says so.
with bounds as (
  select
    fund,
    min(period_end) as first_quarter,
    (date_trunc('quarter', {{ as_of() }}) - interval '1 day')::date as last_quarter
  from {{ ref('stg_statements') }}
  group by fund
),
spine as (
  select b.fund, {{ quarter_end('g') }} as quarter_end
  from bounds b,
  generate_series(b.first_quarter, b.last_quarter, interval '3 months') g
),
accepted as (
  select distinct on (fund, period_end) *
  from {{ ref('int_statement_checks') }}
  where not held
  order by fund, period_end, version desc
),
held as (
  select fund, period_end, bool_or(held) as any_held
  from {{ ref('int_statement_checks') }}
  group by fund, period_end
),
gp_flows as (
  select
    e.gp_fund as fund,
    e.booking_date,
    -- back into the fund's currency at the rate of the day the money moved
    case when tf.currency = 'USD' then -e.amount * {{ usd_per_eur('e.booking_date') }} else -e.amount end as called_ccy,
    0::numeric as distributed_ccy
  from {{ ref('stg_bank_entries') }} e
  join {{ ref('stg_target_funds') }} tf on tf.fund = e.gp_fund
  where e.entry_kind = 'gp_call'
  union all
  select
    e.gp_fund,
    e.booking_date,
    0,
    case when tf.currency = 'USD' then e.amount * {{ usd_per_eur('e.booking_date') }} else e.amount end
  from {{ ref('stg_bank_entries') }} e
  join {{ ref('stg_target_funds') }} tf on tf.fund = e.gp_fund
  where e.entry_kind = 'gp_distribution'
),
filled as (
  select
    s.fund,
    s.quarter_end,
    a.file_id,
    a.version as statement_version,
    coalesce(a.currency, last_a.currency) as currency,
    case when a.file_id is not null then a.nav
         else last_a.nav + coalesce(fl.called, 0) - coalesce(fl.distributed, 0) end as nav_ccy,
    case when a.file_id is not null then a.paid_in else last_a.paid_in + coalesce(fl.called, 0) end as paid_in_ccy,
    case when a.file_id is not null then a.distributed else last_a.distributed + coalesce(fl.distributed, 0) end as distributed_ccy,
    coalesce(a.commitment, last_a.commitment) as commitment_ccy,
    case when a.file_id is not null then 'statement' else 'estimated' end as nav_source,
    case
      when a.file_id is not null then null
      when h.any_held then 'statement held'
      when s.quarter_end + {{ var('statement_due_days') }} < {{ as_of() }} then 'statement late'
      else 'statement not yet due'
    end as estimate_reason,
    last_a.period_end as estimated_from
  from spine s
  left join accepted a on a.fund = s.fund and a.period_end = s.quarter_end
  left join held h on h.fund = s.fund and h.period_end = s.quarter_end
  left join lateral (
    select * from accepted p where p.fund = s.fund and p.period_end < s.quarter_end
    order by p.period_end desc limit 1
  ) last_a on a.file_id is null
  left join lateral (
    select sum(called_ccy) as called, sum(distributed_ccy) as distributed
    from gp_flows g
    where g.fund = s.fund and g.booking_date > last_a.period_end and g.booking_date <= s.quarter_end
  ) fl on a.file_id is null
)
select
  f.*,
  tf.feeder,
  case when f.currency = 'USD' then {{ usd_per_eur('f.quarter_end') }} else 1 end as usd_per_eur,
  round(case when f.currency = 'USD' then f.nav_ccy / {{ usd_per_eur('f.quarter_end') }} else f.nav_ccy end, 2) as nav_eur
from filled f
join {{ ref('stg_target_funds') }} tf using (fund)
where f.nav_ccy is not null
