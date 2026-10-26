select subscription_id, client_key, feeder, amount, signed_on
from {{ source('raw', 'commitments') }}
where signed_on <= {{ as_of() }}
