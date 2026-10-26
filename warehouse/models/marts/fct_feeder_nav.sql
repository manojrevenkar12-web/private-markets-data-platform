select q.*, f.feeder_name
from {{ ref('int_feeder_quarters') }} q
join {{ ref('stg_feeders') }} f using (feeder)
