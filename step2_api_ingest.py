import os
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from minio import Minio
import time
import psutil


start_time = time.time()
# Load variables from the .env file
load_dotenv()

def fetch_openfec_data(endpoint_path, api_key, params=None):
    """Fetches data from OpenFEC API handling pagination and timeouts safely."""
    url = f"https://api.open.fec.gov/v1{endpoint_path}"
    if params is None:
        params = {}
    
    query_params = params.copy()
    query_params['api_key'] = api_key
    query_params['per_page'] = 100
    
    all_results = []
    page = 1
    
    print(f"📡 Querying API endpoint: {endpoint_path}")
    
    while True:
        print(f"   Fetching page {page}...")
        
        # --- RETRY LOGIC FOR THE 504 TIMEOUT ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=query_params, timeout=30) # Explicit timeout
                
                if response.status_code == 200:
                    break  # Success! Break the retry loop
                    
                elif response.status_code in [502, 504]:
                    print(f"   ⏳ Server timed out ({response.status_code}). Retrying attempt {attempt + 1}/{max_retries}...")
                    time.sleep(5)  # Wait 5 seconds before trying again
                else:
                    # Other API errors (like 400 Bad Request) won't fix themselves with a retry
                    print(f"   ❌ API Error ({response.status_code}): {response.text}")
                    return all_results  # Return what we have so far instead of crashing
                    
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Network issue: {e}. Retrying...")
                time.sleep(5)
        else:
            print("   ❌ Max retries reached. Moving forward with data collected so far.")
            return all_results
        # ----------------------------------------
            
        data = response.json()
        results = data.get('results', [])
        all_results.extend(results)
        
        pagination = data.get('pagination', {})
        last_indexes = pagination.get('last_indexes', {})
        
        if not last_indexes or len(results) < 100:
            break
            
        query_params.update(last_indexes)
        page += 1
        
        if page > 5:
            print("   ⚠️ Guard rail triggered: Stopping after 5 pages to preserve API limits.")
            break
            
    return all_results

def main():
    # 1. Retrieve config from environment variables safely
    api_key = os.getenv("OPENFEC_API_KEY")
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    
    # 2. Connect to MinIO
    client = Minio(
        minio_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False
    )
    bucket_name = "data"

    # 3. Base parameters for the 2026 cycle sorting by newest first
    base_params = {
        "cycle": 2026,
        "sort": "-two_year_transaction_period" # Ideal sort for schedules; defaults to descending
    }

    # 4. Dictionary mapping endpoints to a descriptive file prefix
    endpoints_to_fetch = {
        "/candidates/": {
            "file_prefix": "api_raw_candidates",
            "params": {"cycle": 2026, "sort": "-candidate_id"}
        },
        "/committees/": {
            "file_prefix": "api_raw_committees", 
            "params": {"cycle": 2026, "sort": "-first_file_date"}
        },
        "/schedules/schedule_a/": {
            "file_prefix": "api_raw_individual_contribs", 
            "params": {
                "two_year_transaction_period": 2026, # Added to satisfy the API's mandatory filter requirement
                "sort": "-contribution_receipt_date"
            }
        },
        "/schedules/schedule_b/": {
            "file_prefix": "api_raw_committee_disbursements", 
            "params": {
                "two_year_transaction_period": 2026, # Added for consistency and safety across schedules
                "sort": "-disbursement_date"
            }
        },
        "/schedules/schedule_e/": {
            "file_prefix": "api_raw_independent_expenditures", 
            "params": {
                "cycle": 2026, 
                "sort": "-expenditure_date"
            }
        }
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 5. Loop through all transactional targets
    for endpoint, config in endpoints_to_fetch.items():
        print(f"\n--- Starting Ingestion for {endpoint} ---")
        
        raw_api_data = fetch_openfec_data(endpoint, api_key, params=config["params"])
        
        if not raw_api_data:
            print(f"⚠️ No data retrieved from {endpoint}. Skipping file creation.")
            continue
            
        print(f"✅ Successfully retrieved {len(raw_api_data)} records.")

        # Convert JSON API structure directly to a clean Pandas dataframe
        df = pd.DataFrame(raw_api_data)
        
        # Ensure all data elements are saved natively as strings to avoid type corruption
        df = df.astype(str)

        # Save as an API-sourced Bronze Parquet file
        parquet_filename = f"{config['file_prefix']}_{timestamp}.parquet"
        local_temp_path = os.path.join(os.getcwd(), parquet_filename)
        
        df.to_parquet(local_temp_path, engine="pyarrow", compression="snappy")

        # Upload to the incoming/ landing zone inside the Bronze layer
        minio_path = f"bronze/incoming_api/{parquet_filename}"
        client.fput_object(bucket_name, minio_path, local_temp_path)
        print(f"🚀 API Bronze file uploaded cleanly to: {bucket_name}/{minio_path}")

        # Clean up local system temp file
        if os.path.exists(local_temp_path):
            os.remove(local_temp_path)

    print("\n🎉 All API Bronze ingestions completed successfully.")

if __name__ == "__main__":
    main()

end_time = time.time()
runtime_seconds = end_time - start_time

print(f"⏱️ Runtime: {runtime_seconds:.2f} seconds")

# Capture peak memory footprint (Resident Set Size) of the process
process = psutil.Process(os.getpid())
peak_memory_bytes = process.memory_info().peak_wset  # Works perfectly on Windows
# If running on Linux/Mac, use: peak_memory_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

peak_memory_mb = peak_memory_bytes / (1024 * 1024)
print(f"\n📊 [MEMORY PROFILE]: Peak RAM consumption: {peak_memory_mb:.2f} MB")