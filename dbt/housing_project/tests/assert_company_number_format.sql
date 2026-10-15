select 'company_number_format', company_key
from {{ ref('dim_company') }}
where length(company_number) <> 8
