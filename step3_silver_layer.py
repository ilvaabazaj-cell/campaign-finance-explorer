import os
import io
import duckdb
import pandas as pd
from minio import Minio
from dotenv import load_dotenv
import time
import psutil

start_time = time.time()
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
LOCAL_BRONZE_DIR = os.path.join("minio_data", "data", "bronze")
SILVER_PREFIX = "silver/"

MAPPINGS = {
    "committee_master": {
        "bulk": {"CMTE_ID": "com_id", "CMTE_NM": "com_name", "CMTE_CITY": "com_city", "CMTE_ST": "com_state", "CMTE_ZIP": "com_zip", "CMTE_DSGN": "com_design", "CMTE_TP": "com_type", "CMTE_PTY_AFFILIATION": "com_party", "CAND_ID": "cand_id"},
        "api": {"committee_id": "com_id", "name": "com_name", "designation_full": "com_design", "committee_type_full": "com_type", "party_full": "com_party", "candidate_ids": "cand_id"}
    },
    "candidate_master": {
        "bulk": {"CAND_ID": "cand_id", "CAND_NAME": "cand_name", "CAND_PTY_AFFILIATION": "cand_party", "CAND_ELECTION_YR": "cand_el_yr", "CAND_OFFICE_ST": "cand_off_state", "CAND_OFFICE": "cand_off", "CAND_PCC": "com_id"},
        "api": {"candidate_id": "cand_id", "name": "cand_name", "party_full": "cand_party", "election_years": "cand_el_yr", "state": "cand_off_state", "office_full": "cand_off", "principal_committees": "com_id"}
    },
    "individual_contributions": {
        "bulk": {"CMTE_ID": "com_id", "TRANSACTION_PGI": "election_type", "NAME": "contrib_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "EMPLOYER": "contrib_emp", "OCCUPATION": "contrib_occ", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id"},
        "api": {"committee_id": "com_id", "election_type_full": "election_type", "contributor_name": "contrib_name", "contributor_city": "contrib_city", "contributor_state": "contrib_state", "contributor_zip": "contrib_zip", "contributor_employer": "contrib_emp", "contributor_occupation": "contrib_occ", "contribution_receipt_date": "trans_date", "contribution_receipt_amount": "trans_amt", "contributor_id": "other_com_id"}
    },
    #"candidate_committee_linkages": {
     #   "bulk": {"CAND_ID": "cand_id", "CAND_ELECTION_YR": "cand_el_yr", "FEC_ELECTION_YR": "fec_el_yr", "CMTE_ID": "com_id", "CMTE_TP": "com_type", "CMTE_DSGN": "com_design"},
      #  "api": {"candidate_id": "cand_id", "election_year": "cand_el_yr", "cycles": "fec_el_yr", "committee_id": "com_id", "committee_type_full": "com_type", "designation_full": "com_design"}
    #},
    "inter_committee_transactions": {
        "bulk": {"CMTE_ID": "com_id", "TRANSACTION_PGI": "election_type", "TRANSACTION_TP": "trans_type", "ENTITY_TP": "entity_tp", "NAME": "entity_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id", "SUB_ID": "sub_id"},
        "api": {"committee_id": "com_id", "election_type_full": "election_type", "transaction_type": "trans_type", "entity_type": "entity_tp", "contributor_name": "entity_name", "contributor_city": "contrib_city", "contributor_state": "contrib_state", "contributor_zip": "contrib_zip", "contribution_receipt_date": "trans_date", "contribution_receipt_amount": "trans_amt", "contributor_id": "other_com_id", "transaction_id": "sub_id"}
    },
    "committee_contributions_to_candidates": {
        "bulk": {"CMTE_ID": "com_id", "CAND_ID": "cand_id", "TRANSACTION_PGI": "election_type", "TRANSACTION_TP": "trans_type", "ENTITY_TP": "entity_tp", "NAME": "entity_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id", "SUB_ID": "sub_id"},
        "api": {"committee_id": "com_id", "candidate_id": "cand_id", "election_type_full": "election_type", "transaction_type": "trans_type", "entity_type": "entity_tp", "recipient_name": "entity_name", "recipient_city": "contrib_city", "recipient_state": "contrib_state", "recipient_zip": "contrib_zip", "disbursement_date": "trans_date", "disbursement_amount": "trans_amt", "recipient_committee_id": "other_com_id", "transaction_id": "sub_id"}
    },
    "independent_expenditures": {
        "bulk": {"CMTE_ID": "com_id", "TRANSACTION_PGI": "election_type", "TRANSACTION_TP": "trans_type", "ENTITY_TP": "entity_tp", "NAME": "entity_name", "CITY": "contrib_city", "STATE": "contrib_state", "ZIP_CODE": "contrib_zip", "TRANSACTION_DT": "trans_date", "TRANSACTION_AMT": "trans_amt", "OTHER_ID": "other_com_id", "CAND_ID": "cand_id", "SUB_ID": "sub_id"},
        "api": {"committee_id": "com_id", "election_type_full": "election_type", "transaction_type": "trans_type", "entity_type": "entity_tp", "contributor_name": "entity_name", "contributor_city": "contrib_city", "contributor_state": "contrib_state", "contributor_zip": "contrib_zip", "contribution_receipt_date": "trans_date", "contribution_receipt_amount": "trans_amt", "contributor_id": "other_com_id", "candidate_id": "cand_id", "transaction_id": "sub_id"}
    },
    "pac_summary": {
        "bulk": {"CMTE_ID": "com_id", "TTL_RECEIPTS": "total_receipts", "INDV_CONTRIB": "total_indv_contrib", "OTHER_POL_CMTE_CONTRIB": "total_pac_contrib", "TTL_DISB": "total_disbursements", "COH_COP": "cash_on_hand", "IND_EXP": "independent_exp", "NET_CONTRIB": "net_contrib", "CVG_END_DT": "coverage_end_date"},
        "api": {"committee_id": "com_id", "committee_name": "com_name", "receipts": "total_receipts", "individual_itemized_contributions": "total_indv_contrib", "other_political_committee_contributions": "total_pac_contrib", "disbursements": "total_disbursements", "cash_on_hand_end_period": "cash_on_hand", "independent_expenditures": "independent_exp", "net_contributions": "net_contrib", "coverage_end_date": "coverage_end_date"}
    }
}

HEADER_MAPS = {
    "cm.txt": "data_seed/cm_header_file.csv",
    "cn.txt": "data_seed/cn_header_file.csv",
    "itcont.txt": "data_seed/indiv_header_file.csv",
    "itoth.txt": "data_seed/oth_header_file.csv",
    "itpas2.txt": "data_seed/pas2_header_file.csv"
}

def process_dataset(dataset_name, bulk_filename, api_prefix):
    print(f"\n⚙️ Processing layer unification for: [{dataset_name}]")
    
    bulk_path = os.path.join(LOCAL_BRONZE_DIR, bulk_filename)
    output_filename = f"{dataset_name}_clean.parquet"
    local_temp_path = os.path.join(os.getcwd(), output_filename)
    
    con = duckdb.connect(database=':memory:')
    
    # Identify the full target universe of columns mapped for this specific model
    bulk_map = MAPPINGS[dataset_name]["bulk"]
    api_map = MAPPINGS[dataset_name]["api"]
    all_target_columns = sorted(list(set(list(bulk_map.values()) + list(api_map.values()))))

    # -------------------------------------------------------------------------
    # STEP A: DUCKDB PARSING ENGINE FOR BULK DATA
    # -------------------------------------------------------------------------
    has_bulk = False
    if os.path.exists(bulk_path):
        header_file = HEADER_MAPS.get(bulk_filename)
        if header_file and os.path.exists(header_file):
            header_df = pd.read_csv(header_file, nrows=0)
            columns = header_df.columns.tolist()
            
            # Map columns explicitly; fill missing ones with NULL to align schemas
            select_items = []
            for target_col in all_target_columns:
                # Find matching raw historical column name
                matched_source = [k for k, v in bulk_map.items() if v == target_col and k in columns]
                if matched_source:
                    select_items.append(f"\"{matched_source[0]}\" AS {target_col}")
                else:
                    select_items.append(f"CAST(NULL AS VARCHAR) AS {target_col}")
            
            select_clause = ", ".join(select_items)
            
            print(f"   📥 Streaming massive file natively via DuckDB: {bulk_path}")
            try:
                con.execute(f"""
                    CREATE VIEW bulk_raw_view AS 
                    SELECT {select_clause} FROM read_csv('{bulk_path}', 
                                                           sep='|', 
                                                           header=False, 
                                                           names={columns}, 
                                                           all_varchar=True,
                                                           parallel=True)
                """)
                has_bulk = True
                cnt = con.execute("SELECT count(*) FROM bulk_raw_view").fetchone()[0]
                print(f"   ✅ DuckDB registered {cnt} raw historical records in-view.")
            except Exception as e:
                print(f"   ⚠️ DuckDB bulk extraction skipped/failed: {e}")
        else:
            print(f"   ⚠️ Header file mapping missing for {bulk_filename}.")
            
    # -------------------------------------------------------------------------
    # STEP B: LOAD INCREMENTAL API LIVE UPDATE LOGS
    # -------------------------------------------------------------------------
    df_api = pd.DataFrame()
    try:
        objects = minio_client.list_objects(BUCKET_NAME, prefix="bronze/incoming_api/", recursive=True)
        api_files = [obj.object_name for obj in objects if api_prefix in obj.object_name]
        
        api_dfs = []
        for file_name in api_files:
            response = minio_client.get_object(BUCKET_NAME, file_name)
            parquet_data = io.BytesIO(response.read())
            api_dfs.append(pd.read_parquet(parquet_data))
            
        if api_dfs:
            df_api = pd.concat(api_dfs, ignore_index=True)
            print(f"   📥 Ingested {len(df_api)} real-time incremental records from MinIO.")
    except Exception as e:
        print(f"   ℹ️ No live API increments located for prefix '{api_prefix}': {e}")

    has_api = False
    if not df_api.empty:
        # Build matching data structure using Pandas to keep code cleanly structured
        df_api_aligned = pd.DataFrame()
        for target_col in all_target_columns:
            matched_source = [k for k, v in api_map.items() if v == target_col and k in df_api.columns]
            if matched_source:
                df_api_aligned[target_col] = df_api[matched_source[0]].astype(str)
            else:
                df_api_aligned[target_col] = None
                
        con.register('api_raw_df', df_api_aligned)
        has_api = True

    # -------------------------------------------------------------------------
    # STEP C: UNIFY, CLEAN & EXPORT DATA DIRECTLY FROM DUCKDB DISK ENGINE
    # -------------------------------------------------------------------------
    if not has_bulk and not has_api:
        print(f"   ❌ Cancelled pipeline for {dataset_name}: No source inputs available.")
        return

    # Columns match exactly now, preventing any binder configuration failure
    if has_bulk and has_api:
        union_query = "SELECT * FROM bulk_raw_view UNION ALL SELECT * FROM api_raw_df"
    elif has_bulk:
        union_query = "SELECT * FROM bulk_raw_view"
    else:
        union_query = "SELECT * FROM api_raw_df"

    con.execute(f"CREATE VIEW unified_raw AS {union_query}")
    
    # Isolate rows to avoid cross-table duplication between shared itpas2 source files
    filter_clause = "WHERE 1=1"
    if dataset_name == "committee_contributions_to_candidates":
        filter_clause = "WHERE trans_type = '24K'"
    elif dataset_name == "independent_expenditures":
        filter_clause = "WHERE trans_type IN ('24E', '24A')"

    select_clean_items = []
    for c in all_target_columns:
        if c == "trans_date":
            select_clean_items.append("""
                CASE 
                    WHEN trans_date LIKE '%-%' THEN strftime(strptime(trans_date, '%Y-%m-%d'), '%Y-%m-%d')
                    WHEN length(regexp_replace(trans_date, '[^0-9]', '', 'g')) = 8 THEN strftime(strptime(trans_date, '%m%d%Y'), '%Y-%m-%d')
                    ELSE NULL 
                END AS trans_date
            """)
        elif c == "trans_amt":
            select_clean_items.append("COALESCE(CAST(trans_amt AS DOUBLE), 0.0) AS trans_amt")
        elif c in ["cand_id", "com_id", "other_com_id", "sub_id"]:
            # Data Quality: Rimozione spazi e formattazione rigorosa degli ID
            select_clean_items.append(f"TRIM(UPPER(COALESCE(CAST(\"{c}\" AS VARCHAR), ''))) AS \"{c}\"")
        elif c == "contrib_emp":
            # Normalizzazione forte per i datori di lavoro (RIMOZIONE DOPPIONI E SPAZI)
            select_clean_items.append(f"TRIM(UPPER(COALESCE(CAST(\"{c}\" AS VARCHAR), 'NOT SPECIFIED'))) AS \"{c}\"")
        else:
            select_clean_items.append(f"COALESCE(CAST(\"{c}\" AS VARCHAR), '') AS \"{c}\"")

    select_clean_clause = ", ".join(select_clean_items)

    print(f"   🛡️ Unifying schemas and executing deduplication + code separation ({filter_clause})...")
    
    con.execute(f"""
        COPY (
            SELECT DISTINCT {select_clean_clause} 
            FROM unified_raw
            {filter_clause}
        ) TO '{local_temp_path}' (FORMAT PARQUET, COMPRESSION 'SNAPPY')
    """)
    # -------------------------------------------------------------------------
    # STEP D: COMMIT TO MINIO FOR USER INTERFACE DISPLAY
    # -------------------------------------------------------------------------
    try:
        minio_silver_path = f"{SILVER_PREFIX}{dataset_name}/{output_filename}"
        minio_client.fput_object(BUCKET_NAME, minio_silver_path, local_temp_path)
        
        final_count = con.execute(f"SELECT count(*) FROM read_parquet('{local_temp_path}')").fetchone()[0]
        print(f"   ✨ [SILVER LAYER SUCCESS]: Uploaded model to {BUCKET_NAME}/{minio_silver_path} ({final_count} rows)")
        
        if os.path.exists(local_temp_path):
            os.remove(local_temp_path)
            
    except Exception as e:
        print(f"   ❌ Failed to commit silver dataset: {e}")

if __name__ == "__main__":
    pipeline_tasks = [
        ("committee_master", "cm.txt", "api_raw_committees"),
        ("candidate_master", "cn.txt", "api_raw_candidates"),
        ("individual_contributions", "itcont.txt", "api_raw_individual_contribs"),
        ("inter_committee_transactions", "itoth.txt", "api_raw_inter_committee"), 
        ("committee_contributions_to_candidates", "itpas2.txt", "api_raw_committee_disbursements"),
        ("independent_expenditures", "itpas2.txt", "api_raw_independent_expenditures")
    ]
    
    print("🚀 Starting the Memory-Isolated DuckDB Silver Layer Pipeline...")
    for dataset_name, bulk_file, api_prefix in pipeline_tasks:
        process_dataset(dataset_name, bulk_file, api_prefix)
    print("\n🏁 Universal Silver Layer Execution Completed successfully!")

end_time = time.time()
runtime_seconds = end_time - start_time

print(f"⏱️ Runtime: {runtime_seconds:.2f} seconds")

# Capture peak memory footprint (Resident Set Size) of the process
process = psutil.Process(os.getpid())
peak_memory_bytes = process.memory_info().peak_wset  # Works perfectly on Windows
# If running on Linux/Mac, use: peak_memory_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

peak_memory_mb = peak_memory_bytes / (1024 * 1024)
print(f"\n📊 [MEMORY PROFILE]: Peak RAM consumption: {peak_memory_mb:.2f} MB")