select counterparty_key, client_key from {{ source('raw', 'client_accounts') }}
