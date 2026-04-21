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

TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.stock_prices_raw"
client = bigquery.Client(project=PROJECT_ID)

def get_tickers_from_csv():
    """Reads the list of tickers from a local CSV file."""
    print(f"🔍 Loading tickers from {TICKERS_FILE}...")
    try:
        df = pd.read_csv(TICKERS_FILE)
        
        # Check for standard casing
        if 'Ticker' in df.columns:
            tickers = df['Ticker'].dropna().astype(str).tolist()
        elif 'ticker' in df.columns:
            tickers = df['ticker'].dropna().astype(str).tolist()
        else:
            raise ValueError(f"Could not find a 'Ticker' column in {TICKERS_FILE}.")
            
        # Add SPY as the benchmark for your dbt Alpha calculations
        if 'SPY' not in tickers:
            tickers.append('SPY')
            
        return tickers
    
    except Exception as e:
        print(f"Error loading {TICKERS_FILE}: {e}")
        return []

def fetch_and_load_data():
    tickers = get_tickers_from_csv()
    
    if not tickers:
        print("⚠️ No tickers found. Exiting.")
        return

    print(f"🚀 Found {len(tickers)} tickers. Starting 2-year data extraction...\n")
    
    all_dataframes = []
    failed_tickers = []

    # 1. Extract and Transform
    for i, ticker in enumerate(tickers, 1):
        print(f"Processing {i}/{len(tickers)}: {ticker}")
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period="2y")

            if data.empty:
                failed_tickers.append(ticker)
                continue

            df_raw = data.reset_index()

            # Create the clean dataframe for this specific ticker
            df = pd.DataFrame({
                'ticker': ticker,
                'trading_date': pd.to_datetime(df_raw['Date']).dt.date, 
                'adj_close': df_raw['Close'].round(4), 
                'ingested_at': pd.Timestamp.now()
            })

            all_dataframes.append(df)
            
            # Be nice to Yahoo Finance's servers to prevent IP bans
            time.sleep(0.5)

        except Exception as e:
            print(f"  -> Failed to process {ticker}: {e}")
            failed_tickers.append(ticker)

    # 2. Combine Data
    if not all_dataframes:
        print("⚠️ No data was collected. Exiting.")
        return

    print("\n🧩 Compiling all data into a single master table...")
    master_df = pd.concat(all_dataframes, ignore_index=True)
    
    print("\nMaster Data Preview:")
    print(master_df.head())

    # 3. Load to BigQuery (Single Bulk Upload)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE", 
        autodetect=True, 
    )

    print(f"\n📡 Bulk loading {len(master_df)} rows into {TABLE_ID}...")
    job = client.load_table_from_dataframe(master_df, TABLE_ID, job_config=job_config)
    
    job.result()  # Wait for the job to complete
    print(f"✅ Success! Data loaded into BigQuery.")

    # Report any tickers that had issues
    if failed_tickers:
        print(f"\n⚠️ Note: The following {len(failed_tickers)} tickers failed or had no data:")
        print(", ".join(failed_tickers))

if __name__ == "__main__":
    fetch_and_load_data()