with correction_counts as (
    select
        company_key,
        currency_key,
        sum(case when is_correction = true then 1 else 0 end) as correction_count
    from {{ ref('fct_capital_declaration') }}
    group by company_key, currency_key
),

previous_declaration as (
    select
        *,
        lag(declared_amount) over (
            partition by company_key, currency_key order by filed_on, transaction_id
        ) as previous_declared_amount,
        lag(filed_on) over (
            partition by company_key, currency_key order by filed_on, transaction_id
        ) as previous_filed_on,
        lag(filing_type) over (
            partition by company_key, currency_key order by filed_on, transaction_id
        ) as previous_filing_type,
        lag(has_same_day_declarations) over (
            partition by company_key, currency_key order by filed_on, transaction_id
        ) as previous_has_same_day_declarations
    from {{ ref('fct_capital_declaration') }}
),

comparison_rules as (
    select
        declaration.*,
        corrections.correction_count > 0 as has_unresolved_corrections,
        case
            when declaration.previous_filed_on is null then 'no_previous_declaration'
            when corrections.correction_count > 0 then 'unresolved_corrections'
            when declaration.has_same_day_declarations or declaration.previous_has_same_day_declarations
                then 'ambiguous_order'
            when declaration.filing_type <> declaration.previous_filing_type then 'different_filing_types'
            when declaration.declared_amount is null or declaration.previous_declared_amount is null
                then 'missing_amount'
            when coalesce(rules.is_comparable, false) = false then 'comparability_not_approved'
            else 'comparable'
        end as comparison_status
    from previous_declaration as declaration
    join correction_counts as corrections
        on declaration.company_key = corrections.company_key
        and declaration.currency_key = corrections.currency_key
    left join {{ ref('capital_comparison_rules') }} as rules
        on declaration.filing_type = rules.filing_type
)

select
    history.*,
    company.company_name,
    case when history.comparison_status = 'comparable'
        then history.declared_amount - history.previous_declared_amount
    end as declared_amount_change,
    case when history.comparison_status = 'comparable'
        then 100.0 * (history.declared_amount - history.previous_declared_amount)
            / nullif(history.previous_declared_amount, 0)
    end as declared_amount_change_pct
from comparison_rules as history
join {{ ref('dim_company') }} as company
    on history.company_key = company.company_key
