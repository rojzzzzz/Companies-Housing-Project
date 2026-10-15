select
    obligation.*,
    company.company_name,
    obligation.observed_date = (
        select max(observed_date) from {{ ref('int_company_observation') }}
    ) as is_latest_observation
from {{ ref('fct_company_obligation_snapshot') }} as obligation
join {{ ref('dim_company') }} as company
    on obligation.company_key = company.company_key
