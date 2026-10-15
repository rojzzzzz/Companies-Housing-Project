select {{ gold_key([company_number('company_number'), 'transaction_id']) }} as filing_key,
       {{ company_number('company_number') }} as company_key,
       transaction_id,
       {{ gold_key(['type', 'category', 'subcategory']) }} as filing_type_key,
       to_char(date, 'YYYYMMDD')::integer as filed_date_key,
       date::date as filed_on, action_date::date as action_on,
       change_date::date as changed_on, made_up_date::date as made_up_on,
       appointment_date::date as appointment_on, termination_date::date as termination_on,
       description, description_value, pages::integer as pages, paper_filed,
       document_metadata, link_self
from {{ source('staging', 'filings') }}
