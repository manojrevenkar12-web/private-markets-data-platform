select fund, feeder, name as fund_name, gp, region, strategy, currency
from {{ source('raw', 'target_funds') }}
