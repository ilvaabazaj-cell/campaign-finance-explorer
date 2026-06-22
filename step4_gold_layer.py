# step4_gold_layer.py
import os
import duckdb
from dotenv import load_dotenv

load_dotenv()

def build_gold_layer():
    print("🚀 Starting Gold Layer Aggregation Engine...")
    
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    bucket_name = "data"
    
    s3_endpoint = minio_endpoint.replace("http://", "").replace("https://", "")

    con = duckdb.connect(database=':memory:')
    
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{s3_endpoint}';")
    con.execute(f"SET s3_access_key_id='{access_key}';")
    con.execute(f"SET s3_secret_access_key='{secret_key}';")
    con.execute("SET s3_url_style='path';")
    con.execute("SET s3_use_ssl=false;")

    gold_dir = os.path.join("minio_data", "data", "gold")
    os.makedirs(gold_dir, exist_ok=True)
    
    base_s3 = f"s3://{bucket_name}/silver"
    paths = {
        "candidate_master": f"{base_s3}/candidate_master/candidate_master_clean.parquet",
        "committee_master": f"{base_s3}/committee_master/committee_master_clean.parquet",
        "individual_contributions": f"{base_s3}/individual_contributions/individual_contributions_clean.parquet",
        "committee_contributions_to_candidates": f"{base_s3}/committee_contributions_to_candidates/committee_contributions_to_candidates_clean.parquet",
        "inter_committee_transactions": f"{base_s3}/inter_committee_transactions/inter_committee_transactions_clean.parquet",
        "independent_expenditures": f"{base_s3}/independent_expenditures/independent_expenditures_clean.parquet"
    }

    for view_name, s3_url in paths.items():
        try:
            con.execute(f"CREATE VIEW silver_{view_name} AS SELECT * FROM read_parquet('{s3_url}')")
        except Exception as e:
            print(f"❌ Failed to link {view_name}: {e}")
            return

    # --- BASE CLEAN VIEW FOR CANDIDATES (Fixes image_175a79.png) ---
    # This regex extracts numbers from brackets, splits them into individual rows, and filters out odd years
    con.execute("""
        CREATE VIEW clean_candidates_base AS
        SELECT 
            cand_id,
            cand_name,
            cand_off,
            CAST(regexp_split_to_table(regexp_replace(cand_el_yr, '\[|\]|\s|''', '', 'g'), ',') AS INTEGER) AS election_cycle
        FROM silver_candidate_master
        WHERE cand_el_yr IS NOT NULL AND cand_el_yr != ''
    """)

    # --- METRIC 1: GEOGRAPHIC DISTRIBUTION ---
    print("📊 Computing Geographic Distribution Table...")
    con.execute("""
        CREATE TABLE geo_summary AS
        SELECT 
            c.cand_id,
            c.cand_name,
            c.cand_off AS office_type,
            c.election_cycle::VARCHAR AS election_cycle,
            i.contrib_state AS state,
            SUM(CAST(i.trans_amt AS DOUBLE)) AS total_amount,
            COUNT(*) AS total_donations
        FROM silver_individual_contributions i
        JOIN silver_committee_master cm ON i.com_id = cm.com_id
        JOIN clean_candidates_base c ON cm.cand_id = c.cand_id
        WHERE i.contrib_state IS NOT NULL AND i.contrib_state != ''
          AND c.election_cycle % 2 = 0 -- Keep only standard even-year cycles
        GROUP BY 1, 2, 3, 4, 5
    """)
    con.execute(f"COPY geo_summary TO '{os.path.join(gold_dir, 'gold_candidate_geo_summary.parquet')}' (FORMAT PARQUET)")

    # --- METRIC 2: DONOR TYPE BREAKDOWN ---
    print("📊 Computing Donor Type Breakdowns...")
    con.execute("""
        CREATE TABLE donor_type_summary AS
        WITH indiv_agg AS (
            SELECT 
                cm.cand_id,
                SUM(CAST(i.trans_amt AS DOUBLE)) AS individual_funds
            FROM silver_individual_contributions i
            JOIN silver_committee_master cm ON i.com_id = cm.com_id
            GROUP BY 1
        ),
        comm_agg AS (
            SELECT 
                cand_id,
                SUM(CAST(trans_amt AS DOUBLE)) AS committee_funds
            FROM silver_committee_contributions_to_candidates
            GROUP BY 1
        )
        SELECT 
            c.cand_id,
            c.cand_name,
            c.election_cycle::VARCHAR AS election_cycle,
            COALESCE(i.individual_funds, 0.0) AS individual_funds,
            COALESCE(cm.committee_funds, 0.0) AS committee_funds
        FROM clean_candidates_base c
        LEFT JOIN indiv_agg i ON c.cand_id = i.cand_id
        LEFT JOIN comm_agg cm ON c.cand_id = cm.cand_id
        WHERE (i.individual_funds > 0 OR cm.committee_funds > 0)
          AND c.election_cycle % 2 = 0
    """)
    con.execute(f"COPY donor_type_summary TO '{os.path.join(gold_dir, 'gold_donor_type_summary.parquet')}' (FORMAT PARQUET)")

    # --- METRIC 3: NETWORK ANALYSIS METRICS ---
    print("🕸️ Compiling Comprehensive Network Analysis Metrics...")
    con.execute("""
        CREATE TABLE network_metrics AS
        SELECT 
            i.contrib_name AS source_node,
            'Individual Donor' AS source_type,
            c.cand_name AS target_node,
            'Direct Campaign Contribution' AS transaction_flow,
            c.election_cycle::VARCHAR AS election_cycle,
            SUM(CAST(i.trans_amt AS DOUBLE)) AS weight,
            COUNT(*) AS transaction_count
        FROM silver_individual_contributions i
        JOIN silver_committee_master cm ON i.com_id = cm.com_id
        JOIN clean_candidates_base c ON cm.cand_id = c.cand_id
        WHERE c.election_cycle % 2 = 0
        GROUP BY 1, 2, 3, 4, 5
        HAVING weight > 15000
        
        UNION ALL
        
        SELECT 
            cm.com_name AS source_node,
            'Committee/PAC' AS source_type,
            c.cand_name AS target_node,
            'PAC to Candidate Contribution' AS transaction_flow,
            c.election_cycle::VARCHAR AS election_cycle,
            SUM(CAST(cc.trans_amt AS DOUBLE)) AS weight,
            COUNT(*) AS transaction_count
        FROM silver_committee_contributions_to_candidates cc
        JOIN silver_committee_master cm ON cc.com_id = cm.com_id
        JOIN clean_candidates_base c ON cc.cand_id = c.cand_id
        WHERE c.election_cycle % 2 = 0
        GROUP BY 1, 2, 3, 4, 5

        UNION ALL

        SELECT 
            src.com_name AS source_node,
            'Committee/PAC' AS source_type,
            tgt.com_name AS target_node,
            'Inter-PAC Transfer' AS transaction_flow,
            '2026' AS election_cycle, -- Fallback cycle for basic inter-committee movements
            SUM(CAST(ic.trans_amt AS DOUBLE)) AS weight,
            COUNT(*) AS transaction_count
        FROM silver_inter_committee_transactions ic
        JOIN silver_committee_master src ON ic.com_id = src.com_id
        JOIN silver_committee_master tgt ON ic.other_com_id = tgt.com_id
        GROUP BY 1, 2, 3, 4, 5
        HAVING weight > 30000

        UNION ALL

        SELECT 
            cm.com_name AS source_node,
            'Committee/PAC' AS source_type,
            c.cand_name AS target_node,
            'Independent Expenditure (IE)' AS transaction_flow,
            c.election_cycle::VARCHAR AS election_cycle,
            SUM(CAST(ie.trans_amt AS DOUBLE)) AS weight,
            COUNT(*) AS transaction_count
        FROM silver_independent_expenditures ie
        JOIN silver_committee_master cm ON ie.com_id = cm.com_id
        JOIN clean_candidates_base c ON ie.other_com_id = c.cand_id
        WHERE c.election_cycle % 2 = 0
        GROUP BY 1, 2, 3, 4, 5
    """)
    con.execute(f"COPY network_metrics TO '{os.path.join(gold_dir, 'gold_network_metrics.parquet')}' (FORMAT PARQUET)")

    print("✨ Gold Layer Fixed! Run dashboard.py next.")

if __name__ == "__main__":
    build_gold_layer()