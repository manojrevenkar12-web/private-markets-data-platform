-- Through the feeder to the funds underneath, for the latest quarter: what a client owns in each fund.
with latest as (
  select feeder, max(quarter_end) as quarter_end from {{ ref('int_feeder_quarters') }} group by feeder
),
pos as (
  select p.* from {{ ref('fct_client_positions') }} p join latest l using (feeder, quarter_end)
)
select
  pos.client_key, pos.feeder, pos.quarter_end, f.fund, f.fund_name, f.strategy, f.region, f.currency,
  round(f.nav_eur * pos.commitment / fq.total_commitment, 2) as nav_eur, f.nav_source, f.estimate_reason
from pos
join {{ ref('fct_fund_nav') }} f on f.feeder = pos.feeder and f.quarter_end = pos.quarter_end
join {{ ref('int_feeder_quarters') }} fq on fq.feeder = pos.feeder and fq.quarter_end = pos.quarter_end
union all
select
  pos.client_key, pos.feeder, pos.quarter_end, null, 'Cash at the feeder', 'Cash', null, 'EUR',
  round(fq.cash_eur * pos.commitment / fq.total_commitment, 2), 'bank', null
from pos
join {{ ref('int_feeder_quarters') }} fq on fq.feeder = pos.feeder and fq.quarter_end = pos.quarter_end
