select
    {{ gold_key([company_number('capital.company_number'), 'capital.transaction_id', 'upper(trim(capital.currency))']) }} as capital_declaration_key,
    {{ company_number('capital.company_number') }} as company_key,
    filing.filing_key,
    filing.filing_type_key,
    filing.filed_date_key,
    filing.filed_on,
    capital.transaction_id,
    upper(trim(capital.currency)) as currency_key,
    cast(nullif(trim(capital.figure::text), '') as numeric) as declared_amount,
    filing_type.filing_type,
    filing_type.filing_type like 'RP%' as is_correction,
    -- Multiple declarations on one day cannot be ordered reliably by date.
    count(*) over (
        partition by capital.company_number, upper(trim(capital.currency)), filing.filed_on
    ) > 1 as has_same_day_declarations
from {{ source('staging', 'capital') }} as capital
join {{ ref('fct_filing') }} as filing
    on {{ company_number('capital.company_number') }} = filing.company_key
    and capital.transaction_id = filing.transaction_id
join {{ ref('dim_filing_type') }} as filing_type
    on filing.filing_type_key = filing_type.filing_type_key
