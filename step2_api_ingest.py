import os
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from minio import Minio

# Load variables from the .env file
load_dotenv()

def fetch_openfec_data(endpoint_path, api_key, params=None):
    """Fetches data from OpenFEC API handling pagination safely."""
    url = f"https://api.open.fec.gov/v1{endpoint_path}"
    if params is None:
        params = {}
    
    params['api_key'] = api_key
    params['per_page'] = 100  # API limitation limit per page
    
    all_results = []
    page = 1
    
    print(f"📡 Querying API endpoint: {endpoint_path}")
    
    while True:
        print(f"   Fetching page {page}...")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"   ❌ API Error ({response.status_code}): {response.text}")
            break
            
        data = response.json()
        results = data.get('results', [])
        all_results.extend(results)
        
        # Check pagination keys safely
        pagination = data.get('pagination', {})
        last_indexes = pagination.get('last_indexes', {})
        
        # If there are no more pages or last_indexes is empty, stop looping
        if not last_indexes or len(results) < 100:
            break
            
        # Update the query parameters with the pagination pointer for the next page
        params.update(last_indexes)
        page += 1
        
        # Guard rail for university testing so you don't exhaust your 1000 calls limit
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

    # 3. Parameters for incremental nightly pull (sorting by newest first)
    committee_params = {
        "cycle": 2026,
        "sort": "-first_file_date"  # Adding a minus (-) sorts in descending order (newest first!)
    }

    # 4. Run API pull for Committees
    raw_api_data = fetch_openfec_data("/committees/", api_key, params=committee_params)
    
    if not raw_api_data:
        print("❌ No data retrieved from the API. Check your API key or parameters.")
        return
        
    print(f"✅ Successfully retrieved {len(raw_api_data)} records from OpenFEC API.")

    # 5. Convert JSON API structure directly to a clean Pandas dataframe
    df = pd.DataFrame(raw_api_data)
    # Ensure all data elements are saved natively as strings to avoid type corruption
    df = df.astype(str)

    # 6. Save as an API-sourced Bronze Parquet file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_filename = f"api_raw_committees_{timestamp}.parquet"
    local_temp_path = os.path.join(os.getcwd(), parquet_filename)
    
    df.to_parquet(local_temp_path, engine="pyarrow", compression="snappy")

    # 7. Upload to the incoming/ landing zone inside the Bronze layer
    minio_path = f"bronze/incoming_api/{parquet_filename}"
    client.fput_object(bucket_name, minio_path, local_temp_path)
    print(f"🚀 API Bronze file uploaded cleanly to: {bucket_name}/{minio_path}")

    # Clean up local system temp file
    if os.path.exists(local_temp_path):
        os.remove(local_temp_path)

if __name__ == "__main__":
    main()