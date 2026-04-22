with source as (
    select * from {{ source('yfinance', 'raw_stock_metadata') }}
)

select 
    ticker as ticker
    , company_name as company_name
    , industry as industry
    , ingested_at as ingestion_timestamp
from source 
