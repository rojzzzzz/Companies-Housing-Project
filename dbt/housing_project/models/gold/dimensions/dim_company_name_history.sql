-- Previous registered names only. Current name is in dim_company.
select {{ gold_key([company_number('company_number'), 'effective_from::text']) }} as company_name_key,
       {{ company_number('company_number') }} as company_key,
       name as company_name, effective_from, ceased_on
from {{ source('staging', 'previous_company_names') }}
