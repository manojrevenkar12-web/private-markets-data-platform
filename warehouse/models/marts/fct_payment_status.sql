select p.*, f.feeder_name
from {{ ref('int_payment_status') }} p
join {{ ref('stg_feeders') }} f using (feeder)
