select fund, feeder, currency, commitment from {{ source('raw', 'target_commitments') }}
