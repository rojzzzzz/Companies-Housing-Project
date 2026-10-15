-- Find the most recent observation for each company.
with latest_observation as (
    select company_key, max(observed_date) as observed_date
    from {{ ref('int_company_observation') }}
    group by company_key
)

select
    company.company_key,
    company.company_key as company_number,
    company.company_name,
    company.company_status,
    company.company_type,
    company.jurisdiction,
    company.date_of_creation,
    company.address_line_1,
    company.address_line_2,
    company.locality,
    company.postal_code,
    company.country,
    company.can_file,
    company.has_been_liquidated,
    company.has_charges,
    company.has_insolvency_history,
    company.registered_office_is_in_dispute,
    company.undeliverable_registered_office_address,
    company.has_super_secure_pscs,
    company.observed_date as last_observed_date
from {{ ref('int_company_observation') }} as company
join latest_observation as latest
    on company.company_key = latest.company_key
    and company.observed_date = latest.observed_date
