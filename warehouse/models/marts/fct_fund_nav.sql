-- Every target fund's NAV per quarter, in its currency and in EUR, with where the number came from.
select
  q.fund, tf.fund_name, tf.gp, tf.strategy, tf.region, q.feeder, q.quarter_end, q.currency,
  q.commitment_ccy, q.paid_in_ccy, q.distributed_ccy, q.nav_ccy, q.usd_per_eur, q.nav_eur,
  q.nav_source, q.estimate_reason, q.estimated_from, q.file_id as statement_file_id, q.statement_version,
  case when q.paid_in_ccy > 0 then round((q.distributed_ccy + q.nav_ccy) / q.paid_in_ccy, 4) end as tvpi
from {{ ref('int_fund_quarters') }} q
join {{ ref('stg_target_funds') }} tf using (fund)
