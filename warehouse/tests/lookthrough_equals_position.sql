-- Looking through the feeder loses no money: the funds plus cash add up to the client's position.
select l.client_key, l.feeder, sum(l.nav_eur) as through, max(p.nav_eur) as position
from {{ ref('fct_client_lookthrough') }} l
join {{ ref('fct_client_positions') }} p using (client_key, feeder, quarter_end)
group by l.client_key, l.feeder
having abs(sum(l.nav_eur) - max(p.nav_eur)) > 0.05 * count(*)
