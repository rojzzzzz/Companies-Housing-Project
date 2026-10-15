select distinct upper(trim(currency)) as currency_key
from {{ source('staging', 'capital') }}
