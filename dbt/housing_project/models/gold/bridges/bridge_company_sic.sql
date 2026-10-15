select {{ company_number('company_number') }} as company_key,
       lpad(sic_code::text, 5, '0') as sic_key
from {{ source('staging', 'sic_code') }}
