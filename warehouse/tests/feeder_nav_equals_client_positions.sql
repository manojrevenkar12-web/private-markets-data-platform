-- The clients' NAVs add up to the feeder's NAV, to the euro, every quarter.
select p.feeder, p.quarter_end, sum(p.nav_eur) as clients, f.nav_eur as feeder
from {{ ref('fct_client_positions') }} p
join {{ ref('fct_feeder_nav') }} f using (feeder, quarter_end)
group by p.feeder, p.quarter_end, f.nav_eur
having abs(sum(p.nav_eur) - f.nav_eur) > 1 + 0.01 * count(*)
