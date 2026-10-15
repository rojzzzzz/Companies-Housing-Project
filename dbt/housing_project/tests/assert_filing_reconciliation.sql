select 'filing_reconciliation', 'all'
where (select coalesce(sum(filing_count), 0) from {{ ref('mart_filing_activity_monthly') }})
   <> (select count(*) from {{ ref('fct_filing') }} where filed_on <= {{ observation_date() }})
