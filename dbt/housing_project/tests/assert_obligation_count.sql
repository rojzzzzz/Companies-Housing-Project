select 'obligation_count', company_key
from {{ ref('fct_company_obligation_snapshot') }}
group by company_key, observed_date
having count(*) <> 2
