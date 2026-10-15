select 'unsafe_capital_comparison', capital_declaration_key
from {{ ref('mart_declared_capital_history') }}
where comparison_status <> 'comparable'
  and (declared_amount_change is not null or declared_amount_change_pct is not null)
