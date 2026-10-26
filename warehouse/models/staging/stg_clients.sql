select client_key, segment, risk_profile, country, age_band, onboarded_on, advisor, status
from {{ source('raw', 'clients') }}
