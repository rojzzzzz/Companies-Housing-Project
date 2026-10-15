select distinct lpad(sic_code::text, 5, '0') as sic_key
from {{ source('staging', 'sic_code') }}
