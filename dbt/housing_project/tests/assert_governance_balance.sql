-- Reconciliation at business boundaries: zero failing rows expected.
select 'governance_balance' as failure, company_key as entity_key
from {{ ref('mart_governance_monthly') }}
where directors_at_start + appointments - resignations <> active_directors
   or active_directors < 0 or average_active_tenure_days < 0
