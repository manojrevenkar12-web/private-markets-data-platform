-- Clients without personal data: who they are is behind the client key, in pii, for operations only.
select
  c.client_key, c.segment, c.risk_profile, c.country, c.age_band, c.onboarded_on, c.advisor, c.status,
  coalesce(sum(cm.amount), 0) as total_commitment,
  count(distinct cm.feeder) as feeders
from {{ ref('stg_clients') }} c
left join {{ ref('stg_commitments') }} cm using (client_key)
group by 1, 2, 3, 4, 5, 6, 7, 8
