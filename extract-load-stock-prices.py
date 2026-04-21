import yfinance as yf
import pandas as pd
from google.cloud import bigquery
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# 1. Setup Configuration
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")

# Safety check: Prevent the script from running if the .env file is missing or empty
if not PROJECT_ID or not DATASET_ID:
    raise ValueError("⚠️ PROJECT_ID or DATASET_ID not found. Check your .env file.")

TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.raw_stock_prices"

# Initialize BigQuery Client
# Ensure you have run: gcloud auth application-default login
client = bigquery.Client(project=PROJECT_ID)

def fetch_and_load_stock(ticker="AAPL"):
    print(f"🚀 Fetching 2 years of daily data for {ticker}...")
    
    # 2. Extract: Use Ticker().history() for clean, adjusted daily data
    stock = yf.Ticker(ticker)
    data = stock.history(period="2y")

    if data.empty:
        print(f"⚠️ No data found for {ticker}.")
        return

    # 3. Transform: Prepare DataFrame for BigQuery & dbt
    df_raw = data.reset_index()

    # Create a clean DataFrame with exactly the columns dbt needs
    df = pd.DataFrame({
        'ticker': ticker,
        # Convert to Python date object so BQ parses it strictly as a DATE type, not DATETIME
        'trading_date': pd.to_datetime(df_raw['Date']).dt.date, 
        'adj_close': df_raw['Close'].round(4), # 'Close' here is already adjusted
        'ingested_at': pd.Timestamp.now()
    })

    print("\nData Schema:")
    print(df.dtypes)
    print("\nData Preview:")
    print(df.head())

    # 4. Load: Push to BigQuery
    job_config = bigquery.LoadJobConfig(
        # WRITE_TRUNCATE replaces the table entirely (good for testing). 
        # Change to WRITE_APPEND once you are running this on a daily schedule.
        write_disposition="WRITE_TRUNCATE", 
        autodetect=True, # Let BQ infer the schema 
    )

    print(f"\n📡 Loading {len(df)} rows into {TABLE_ID}...")
    job = client.load_table_from_dataframe(df, TABLE_ID, job_config=job_config)
    
    job.result()  # Wait for the job to complete
    print(f"✅ Success! Data loaded into BigQuery.")

if __name__ == "__main__":
    fetch_and_load_stock("AAPL")