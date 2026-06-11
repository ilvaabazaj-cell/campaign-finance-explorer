import os
import io
import pandas as pd
from minio import Minio
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# MinIO native client configuration
minio_endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

host_endpoint = minio_endpoint.replace("http://", "").replace("https://", "")

minio_client = Minio(
    host_endpoint,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

BUCKET_NAME = "data"
BRONZE_PREFIX = "bronze/"
SILVER_PREFIX = "silver/"

# ==========================================
# MAPPING DICTIONARIES (Full 7 Datasets Set)
# ==========================================
MAPPINGS = {
    "committee_master": {
        "bulk": {"CMTE_ID": "com_id", "CMTE_NM": "com_name", "CMTE_CITY": "com_city", "CMTE_ST": "com_state", "CMTE_ZIP": "com_zip", "CMTE_DSGN": "com_design", "CMTE_TP": "com_type", "CMTE_PTY_AFFILIATION": "com_party", "CAND_ID": "cand_id"},
        "api": {"committee_id": "com_id", "name": "com_name", "designated_agent_state": "com_state", "designated_agent_zip": "com_zip", "designation": "com_design", "committee_type": "com_type", "party": "com_party", "candidate_ids": "cand_id"}
    },
    "candidate_master": {
        "bulk": {"CAND_ID": "cand_id", "CAND_NAME": "cand_name", "CAND_PTY_AFFILIATION": "cand_party", "CAND_ELECTION_YR": "cand_el_yr", "CAND_OFFICE_ST": "cand_off_state", "CAND_OFFICE": "cand_off", "CAND_PCC": "com_id"},
        "api": {"candidate_id": "cand_id", "name": "cand_name", "party": "cand_party", "election_years": "cand_el_yr", "state": "cand_off_state", "office": "cand_off", "committee_id": "com_id"}
    },
    "individual_contributions": {
        "bulk": {"CMTE_ID": "com_id", "TRANSACTION_PGI": "election_type", "NAME": "contrib_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "EMPLOYER": "contrib_emp", "OCCUPATION": "contrib_occ", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id"},
        "api": {"committee_id": "com_id", "election_type": "election_type", "contributor_name": "contrib_name", "contributor_city": "contrib_city", "contributor_state": "contrib_state", "contributor_zip": "contrib_zip", "contributor_employer": "contrib_emp", "contributor_occupation": "contrib_occ", "contribution_receipt_date": "trans_date", "contribution_receipt_amount": "trans_amt"}
    },
    "candidate_committee_linkages": {
        "bulk": {"CAND_ID": "cand_id", "CAND_ELECTION_YR": "cand_el_yr", "FEC_ELECTION_YR": "fec_el_yr", "CMTE_ID": "com_id", "CMTE_TP": "com_type", "CMTE_DSGN": "com_design"},
        "api": {"candidate_id": "cand_id", "election_year": "cand_el_yr", "cycles": "fec_el_yr", "committee_id": "com_id", "committee_type": "com_type", "designation": "com_design"}
    },
    "inter_committee_transactions": {
        "bulk": {"CMTE_ID": "com_id", "TRANSACTION_PGI": "election_type", "TRANSACTION_TP": "trans_type", "ENTITY_TP": "entity_tp", "NAME": "entity_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id", "SUB_ID": "sub_id"},
        "api": {"committee_id": "com_id", "election_type": "election_type", "transaction_type": "trans_type", "entity_type": "entity_tp", "contributor_name": "entity_name", "contributor_city": "contrib_city", "contributor_state": "contrib_state", "contributor_zip": "contrib_zip", "contribution_receipt_date": "trans_date", "contribution_receipt_amount": "trans_amt", "contributor_id": "other_com_id", "transaction_id": "sub_id"}
    },
    "committee_contributions_to_candidates": {
        "bulk": {"CMTE_ID": "com_id", "CAND_ID": "cand_id", "TRANSACTION_PGI": "election_type", "TRANSACTION_TP": "trans_type", "ENTITY_TP": "entity_tp", "NAME": "entity_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id", "SUB_ID": "sub_id"},
        "api": {"committee_id": "com_id", "candidate_id": "cand_id", "election_type": "election_type", "transaction_type": "trans_type", "entity_type": "entity_tp", "recipient_name": "entity_name", "recipient_city": "contrib_city", "recipient_state": "contrib_state", "recipient_zip": "contrib_zip", "disbursement_date": "trans_date", "disbursement_amount": "trans_amt", "recipient_committee_id": "other_com_id", "transaction_id": "sub_id"}
    },
    "pac_summary": {
        "bulk": {"CMTE_ID": "com_id", "CMTE_NM": "com_name", "TTL_RECEIPTS": "total_receipts", "INDV_CONTRIB": "total_indv_contrib", "OTHER_POL_CMTE_CONTRIB": "total_pac_contrib", "TTL_DISB": "total_disbursements", "COH_COP": "cash_on_hand", "IND_EXP": "independent_exp", "NET_CONTRIB": "net_contrib", "CVG_END_DT": "coverage_end_date"},
        "api": {"committee_id": "com_id", "receipts": "total_receipts", "individual_itemized_contributions": "total_indv_contrib", "other_political_committee_contributions": "total_pac_contrib", "disbursements": "total_disbursements", "cash_on_hand_end_period": "cash_on_hand", "independent_expenditures": "independent_exp", "net_contributions": "net_contrib", "coverage_end_date": "coverage_end_date"}
    }
}

def load_df_from_minio(file_path):
    """Detects file format in Bronze and loads it using the native Minio client."""
    try:
        response = minio_client.get_object(BUCKET_NAME, file_path)
        data_bytes = response.read()
        response.close()
        response.release_conn()
        
        if file_path.endswith(".parquet"):
            return pd.read_parquet(io.BytesIO(data_bytes))
        elif file_path.endswith(".json"):
            return pd.read_json(io.BytesIO(data_bytes))
        else:
            return pd.read_csv(io.BytesIO(data_bytes), sep="|", on_bad_lines='skip')
    except Exception as e:
        print(f"⚠️ Bulk file not found or unreadable: {file_path}")
        return None

def find_latest_api_file(prefix_search):
    """Finds the most recent timestamped API file in the MinIO bucket."""
    try:
        objects = minio_client.list_objects(BUCKET_NAME, prefix=f"{BRONZE_PREFIX}incoming_api/", recursive=True)
        matching_files = [obj.object_name for obj in objects if prefix_search in obj.object_name]
        if matching_files:
            return sorted(matching_files)[-1]
    except Exception:
        pass
    return None

def normalize_dates(series):
    """Synchronizes dates into a single standard YYYY-MM-DD format."""
    series = series.astype(str).str.split('.').str[0].str.strip()
    def parse_row(val):
        if len(val) == 8 and val.isdigit():
            return pd.to_datetime(val, format='%m%d%Y', errors='coerce')
        return pd.to_datetime(val, errors='coerce')
    return series.apply(parse_row).dt.strftime('%Y-%m-%d')

def process_layer(dataset_name, bulk_filename, api_search_pattern):
    print(f"\n⚙️ Normalizing dataset: {dataset_name}")
    dfs = []
    
    # 1. Load Bulk data
    df_bulk = load_df_from_minio(f"{BRONZE_PREFIX}{bulk_filename}")
    if df_bulk is not None:
        df_bulk = df_bulk.rename(columns=MAPPINGS[dataset_name]["bulk"])
        df_bulk = df_bulk[[c for c in MAPPINGS[dataset_name]["bulk"].values() if c in df_bulk.columns]].copy()
        df_bulk['data_source'] = 'bulk'
        dfs.append(df_bulk)
        
    # 2. Find and load latest API file
    api_filename = find_latest_api_file(api_search_pattern)
    if api_filename:
        print(f"🔍 Found latest API file: {api_filename}")
        df_api = load_df_from_minio(api_filename)
        if df_api is not None:
            df_api = df_api.rename(columns=MAPPINGS[dataset_name]["api"])
            df_api = df_api[[c for c in MAPPINGS[dataset_name]["api"].values() if c in df_api.columns]].copy()
            df_api['data_source'] = 'api'
            dfs.append(df_api)
    else:
        print(f"⚠️ No API files found matching pattern: {api_search_pattern}")

    if not dfs:
        print(f"❌ No source data found in Bronze for {dataset_name}. Skipping.")
        return

    # 3. Consolidation
    master_df = pd.concat(dfs, ignore_index=True)

    # 4. Date Cleaning
    for date_col in ['trans_date', 'coverage_end_date']:
        if date_col in master_df.columns:
            master_df[date_col] = normalize_dates(master_df[date_col])

    # 5. Deduplication
    if 'sub_id' in master_df.columns:
        master_df = master_df.sort_values(by='data_source', ascending=False)
        master_df = master_df.drop_duplicates(subset=['sub_id'], keep='first')
    else:
        cols_to_check = [c for c in master_df.columns if c != 'data_source']
        master_df = master_df.drop_duplicates(subset=cols_to_check, keep='first')

    for col in MAPPINGS[dataset_name]["bulk"].values():
        if col not in master_df.columns:
            master_df[col] = None

    # 6. Upload into Silver Layer
    output_key = f"{SILVER_PREFIX}{dataset_name}.parquet"
    buffer = io.BytesIO()
    master_df.to_parquet(buffer, index=False)
    file_size = buffer.tell()
    buffer.seek(0)
    
    minio_client.put_object(
        BUCKET_NAME, 
        output_key, 
        data=buffer, 
        length=file_size,
        content_type="application/octet-stream"
    )
    print(f"✨ [SILVER LAYER] Successfully created: {output_key} ({len(master_df)} rows)")

if __name__ == "__main__":
    # Standardized task list matching your team's file naming patterns
    pipeline_tasks = [
        ("committee_master", "cm_sample.parquet", "api_raw_committees"),
        ("candidate_master", "cn_sample.parquet", "api_raw_candidates"),
        ("individual_contributions", "indiv_sample.parquet", "api_raw_individual"),
        ("candidate_committee_linkages", "link_sample.parquet", "api_raw_linkages"),
        ("inter_committee_transactions", "itcont_sample.parquet", "api_raw_inter_committee"),
        ("committee_contributions_to_candidates", "pas2_sample.parquet", "api_raw_cmte_contrib"),
        ("pac_summary", "webk_sample.parquet", "api_raw_pac_summary")
    ]
    
    print("🚀 Starting the Universal Silver Layer cleaning pipeline...")
    for dataset, bulk, api_pattern in pipeline_tasks:
        process_layer(dataset, bulk, api_pattern)
    print("\n🏁 The Silver Layer pipeline execution has finished!")