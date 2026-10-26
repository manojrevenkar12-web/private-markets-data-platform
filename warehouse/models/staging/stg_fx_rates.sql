select rate_date, usd_per_eur from {{ source('raw', 'fx_rates') }}
