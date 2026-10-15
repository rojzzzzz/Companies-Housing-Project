select distinct
    {{ gold_key(['type', 'category', 'subcategory']) }} as filing_type_key,
    type as filing_type, category, subcategory
from {{ source('staging', 'filings') }}
