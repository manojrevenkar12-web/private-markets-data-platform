select feeder, name as feeder_name, collection_account, first_close, min_ticket
from {{ source('raw', 'feeders') }}
