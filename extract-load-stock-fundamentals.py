# Script used to extract and load stock fundamentals data into a GBQ 
import os
import time
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from google.cloud import bigquery

# Load environment variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
TICKERS_FILE = 'tickers.csv'
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")

if not PROJECT_ID or not DATASET_ID:
    raise ValueError("⚠️ PROJECT_ID or DATASET_ID not found. Check your .env file.")

# Notice the new table name for your fundamental data
TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.raw_stock_fundamentals"
client = bigquery.Client(project=PROJECT_ID)

def get_tickers_from_csv():
    """Reads the list of tickers from a local CSV file."""
    print(f"🔍 Loading tickers from {TICKERS_FILE}...")
    try:
        df = pd.read_csv(TICKERS_FILE)
        
        if 'Ticker' in df.columns:
            tickers = df['Ticker'].dropna().astype(str).tolist()
        elif 'ticker' in df.columns:
            tickers = df['ticker'].dropna().astype(str).tolist()
        else:
            raise ValueError(f"Could not find a 'Ticker' column in {TICKERS_FILE}.")
            
        return tickers
    
    except Exception as e:
        print(f"Error loading {TICKERS_FILE}: {e}")
        return []

def safe_get(info_dict, key, default=None):
    """Safely extracts a float value from the yfinance info dictionary."""
    val = info_dict.get(key)
    return float(val) if val is not None else default

def fetch_and_load_fundamentals():
    tickers = get_tickers_from_csv()
    
    if not tickers:
        print("⚠️ No tickers found. Exiting.")
        return

    print(f"🚀 Found {len(tickers)} tickers. Extracting fundamental data...\n")
    
    all_dataframes = []
    failed_tickers = []

    # 1. Extract and Transform
    for i, ticker in enumerate(tickers, 1):
        print(f"Processing {i}/{len(tickers)}: {ticker}")
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # If the info dictionary is empty or missing the symbol, skip it
            if not info or 'symbol' not in info:
                failed_tickers.append(ticker)
                continue

            # Map the exact fields needed for your dbt pipeline
            df = pd.DataFrame([{
                'ticker': ticker,
                'revenue_growth_yoy': safe_get(info, 'revenueGrowth'),
                'operating_margin': safe_get(info, 'operatingMargins'),
                'roe': safe_get(info, 'returnOnEquity'),
                'sales_per_share': safe_get(info, 'revenuePerShare'),
                'ps_ratio': safe_get(info, 'priceToSalesTrailing12Months'),
                'last_updated_date': pd.Timestamp.now().date()
            }])

            all_dataframes.append(df)
            
            # Pause to respect Yahoo Finance's rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f"  -> Failed to process {ticker}: {e}")
            failed_tickers.append(ticker)

    # 2. Combine Data
    if not all_dataframes:
        print("⚠️ No data was collected. Exiting.")
        return

    print("\n🧩 Compiling fundamentals into a single master table...")
    master_df = pd.concat(all_dataframes, ignore_index=True)
    
    print("\nMaster Data Preview:")
    print(master_df.head())

    # 3. Load to BigQuery
    job_config = bigquery.LoadJobConfig(
        # We use WRITE_TRUNCATE here because this table represents the "latest snapshot".
        # We don't need a historical log of fundamentals, only the most current values for dbt.
        write_disposition="WRITE_TRUNCATE", 
        autodetect=True, 
    )

    print(f"\n📡 Bulk loading {len(master_df)} rows into {TABLE_ID}...")
    job = client.load_table_from_dataframe(master_df, TABLE_ID, job_config=job_config)
    
    job.result()  # Wait for the job to complete
    print(f"✅ Success! Fundamental data loaded into BigQuery.")

    if failed_tickers:
        print(f"\n⚠️ Note: The following {len(failed_tickers)} tickers failed or had missing data:")
        print(", ".join(failed_tickers))

if __name__ == "__main__":
    fetch_and_load_fundamentals()