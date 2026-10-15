with dates as (
    select date_of_creation::date as d from {{ source('staging', 'company') }}
    union all select date::date from {{ source('staging', 'filings') }}
    union all select appointed_on::date from {{ source('staging', 'officers') }}
    union all select resigned_on::date from {{ source('staging', 'officers') }}
    union all select notified_on::date from {{ ref('int_psc_observation') }}
    union all select ceased_on::date from {{ ref('int_psc_observation') }}
    union all select observed_date from {{ ref('int_company_observation') }}
    union all select next_accounts_due_on::date from {{ ref('int_company_observation') }}
    union all select accounts_next_due::date from {{ ref('int_company_observation') }}
    union all select confirmation_next_due::date from {{ ref('int_company_observation') }}
    union all select {{ observation_date() }}
), bounds as (
    select date_trunc('year', min(d))::date as first_date,
           greatest(max(d), {{ observation_date() }} + interval '2 years')::date as last_date
    from dates
), spine as (
    select generate_series(first_date::timestamp, last_date::timestamp, interval '1 day')::date as date_day
    from bounds
)
select to_char(date_day, 'YYYYMMDD')::integer as date_key, date_day,
       extract(year from date_day)::integer as calendar_year,
       extract(quarter from date_day)::integer as calendar_quarter,
       extract(month from date_day)::integer as calendar_month,
       date_trunc('month', date_day)::date as month_start,
       (date_trunc('month', date_day) + interval '1 month - 1 day')::date as month_end,
       extract(isodow from date_day)::integer as iso_day_of_week,
       extract(isodow from date_day) in (6, 7) as is_weekend
from spine
