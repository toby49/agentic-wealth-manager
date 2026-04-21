#Extracts and loads company names and industries for reporting and sector diversification into GBQ
import os
import time
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from google.cloud import bigquery

# Load environment variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
INPUT_FILE = 'tickers.csv'
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_ID = os.getenv("DATASET_ID")

if not PROJECT_ID or not DATASET_ID:
    raise ValueError("⚠️ PROJECT_ID or DATASET_ID not found. Check your .env file.")

# Define the target table for your metadata
TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.raw_stock_metadata"
client = bigquery.Client(project=PROJECT_ID)

def enrich_and_load_tickers():
    print(f"🔍 Loading {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
        
        # Handle case sensitivity for the ticker column
        if 'Ticker' in df.columns:
            col_name = 'Ticker'
        elif 'ticker' in df.columns:
            col_name = 'ticker'
        else:
            raise ValueError(f"Could not find a 'Ticker' column in {INPUT_FILE}.")
            
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    company_names = []
    industries = []
    failed_tickers = []
    
    print(f"🚀 Fetching metadata for {len(df)} tickers. This may take a few minutes...\n")
    
    for i, row in df.iterrows():
        ticker = str(row[col_name]).strip()
        print(f"Processing {i+1}/{len(df)}: {ticker}")
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Extract name and industry safely
            name = info.get('shortName', info.get('longName', 'Unknown'))
            industry = info.get('industry', 'Unknown')
            
            company_names.append(name)
            industries.append(industry)
            
            # Pause to respect Yahoo Finance's rate limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"  -> Failed to fetch metadata for {ticker}: {e}")
            company_names.append('Unknown')
            industries.append('Unknown')
            failed_tickers.append(ticker)

    # Build the final enriched DataFrame
    enriched_df = pd.DataFrame({
        'ticker': df[col_name].str.strip(),
        'company_name': company_names,
        'industry': industries,
        'ingested_at': pd.Timestamp.now()
    })
    
    print("\n🧩 Master Data Preview:")
    print(enriched_df.head())

    # Load to BigQuery
    job_config = bigquery.LoadJobConfig(
        # Use WRITE_TRUNCATE because this is a static dimension table
        # We want to overwrite the old metadata with the freshest snapshot
        write_disposition="WRITE_TRUNCATE", 
        autodetect=True, 
    )

    print(f"\n📡 Bulk loading {len(enriched_df)} rows into {TABLE_ID}...")
    try:
        job = client.load_table_from_dataframe(enriched_df, TABLE_ID, job_config=job_config)
        job.result()  # Wait for the job to complete
        print(f"✅ Success! Enriched metadata loaded into BigQuery.")
    except Exception as e:
        print(f"❌ Failed to load to BigQuery: {e}")

    if failed_tickers:
        print(f"\n⚠️ Note: The following {len(failed_tickers)} tickers failed to fetch metadata:")
        print(", ".join(failed_tickers))

if __name__ == "__main__":
    enrich_and_load_tickers()