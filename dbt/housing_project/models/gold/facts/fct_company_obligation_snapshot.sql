with accounts as (
    select
        company_key,
        observed_date,
        observed_at,
        'accounts'::text as obligation_type_key,
        -- COALESCE uses the first available value from the two API fields.
        coalesce(next_accounts_due_on, accounts_next_due)::date as due_date,
        coalesce(next_accounts_period_end_on, accounts_next_made_up_to)::date as period_end_date,
        coalesce(next_accounts_overdue, accounts_overdue) as source_overdue_flag,
        coalesce(next_accounts_due_on <> accounts_next_due, false)
            or coalesce(next_accounts_overdue <> accounts_overdue, false) as source_fields_conflict
    from {{ ref('int_company_observation') }}
),

confirmation_statements as (
    select
        company_key,
        observed_date,
        observed_at,
        'confirmation_statement'::text as obligation_type_key,
        confirmation_next_due::date as due_date,
        confirmation_next_made_up_to::date as period_end_date,
        confirmation_overdue as source_overdue_flag,
        false as source_fields_conflict
    from {{ ref('int_company_observation') }}
),

obligations as (
    select * from accounts
    union all
    select * from confirmation_statements
)

select
    {{ gold_key(['company_key', 'obligation_type_key', 'observed_date::text']) }} as obligation_snapshot_key,
    company_key,
    obligation_type_key,
    observed_date,
    observed_at,
    to_char(observed_date, 'YYYYMMDD')::integer as observed_date_key,
    to_char(due_date, 'YYYYMMDD')::integer as due_date_key,
    due_date,
    period_end_date,
    source_overdue_flag,
    source_fields_conflict,
    due_date - observed_date as days_until_due,
    due_date < observed_date as calculated_overdue_flag,
    case
        when source_fields_conflict then 'review_source_conflict'
        when source_overdue_flag = true or due_date < observed_date then 'overdue'
        when due_date is null then 'unknown'
        when due_date <= observed_date + {{ var('obligation_warning_days', 30) }} then 'due_soon'
        else 'later'
    end as follow_up_status
from obligations
