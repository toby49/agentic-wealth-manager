with source as (
    select * from {{ source('yfinance', 'raw_stock_prices') }}
)

select 
    ticker as ticker
    , trading_date as date
    , adj_close as adj_close
    , ingested_at as ingestion_timestamp
from source