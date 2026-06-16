import os
import io
import pandas as pd
import numpy as np
from minio import Minio
from deltalake import DeltaTable
from dotenv import load_dotenv

# Load configuration
load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
host_endpoint = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")

# Initialize MinIO Client
minio_client = Minio(
    host_endpoint,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

BUCKET_NAME = "data"
SILVER_PREFIX = "silver/"
GOLD_PREFIX = "gold/"

# Updated Storage options to fix the "Missing region" Delta Lake error
storage_options = {
    "aws_endpoint_url": f"http://{host_endpoint}",
    "aws_access_key_id": MINIO_ACCESS_KEY,
    "aws_secret_access_key": MINIO_SECRET_KEY,
    "aws_region": "us-east-1",  # Dummy region added for native MinIO compatibility
    "aws_allow_http": "true",
    "aws_s3_allow_unsafe_rename": "true"
}

def upload_gold_parquet(df, filename):
    """Helper to upload a Gold DataFrame directly to MinIO as a Parquet file."""
    try:
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow", compression="snappy")
        buffer.seek(0)
        
        minio_path = f"{GOLD_PREFIX}{filename}"
        minio_client.put_object(
            BUCKET_NAME,
            minio_path,
            buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/octet-stream"
        )
        print(f"✨ [GOLD LAYER] Saved asset to: {BUCKET_NAME}/{minio_path} ({len(df)} rows)")
    except Exception as e:
        print(f"❌ Failed to write Gold asset {filename}: {e}")

def load_silver_table(dataset_name):
    """
    Loads a Silver dataset from MinIO with an automatic fallback strategy:
    1. Tries to read it as a standard Delta Table directory.
    2. Falls back to reading the standalone dataset.parquet file if Delta log is missing.
    """
    # Strategy 1: Attempt native Delta Lake read
    try:
        uri = f"s3://{BUCKET_NAME}/{SILVER_PREFIX}{dataset_name}"
        dt = DeltaTable(uri, storage_options=storage_options)
        return dt.to_pandas()
    except Exception as delta_err:
        print(f"ℹ️ Delta Table loader bypassed for '{dataset_name}' (Reason: {delta_err})")
        print(f"🔄 Attempting direct fallback read from standalone Parquet file...")
        
    # Strategy 2: Fallback to reading the direct target .parquet file from your bucket
    try:
        parquet_blob_path = f"{SILVER_PREFIX}{dataset_name}.parquet"
        response = minio_client.get_object(BUCKET_NAME, parquet_blob_path)
        data_bytes = response.read()
        response.close()
        response.release_conn()
        return pd.read_parquet(io.BytesIO(data_bytes))
    except Exception as pq_err:
        print(f"❌ Critical Error: Unable to recover dataset '{dataset_name}' via Parquet fallback: {pq_err}")
        return None

def build_gold_layer():
    print("🚀 Extracting Silver Tables for Gold Insights Processing...")
    
    # Load foundational datasets via the new self-healing loader
    df_indiv = load_silver_table("individual_contributions")
    df_link = load_silver_table("candidate_committee_linkages")
    df_com_contribs = load_silver_table("committee_contributions_to_candidates")
    df_expenditures = load_silver_table("independent_expenditures")
    
    # Clean money values up front across datasets
    for df in [df_indiv, df_com_contribs, df_expenditures]:
        if df is not None and 'trans_amt' in df.columns:
            df['trans_amt'] = pd.to_numeric(df['trans_amt'], errors='coerce').fillna(0.0)

    # -------------------------------------------------------------------------
    # ANALYSIS 1: NETWORK EDGES & CENTRALITY (Political Cash Flow Graph)
    # -------------------------------------------------------------------------
    print("\n🕸️ Modeling political transaction network edges...")
    edges = []
    
    # Edge Type A: Individual -> Committee
    if df_indiv is not None and len(df_indiv) > 0:
        indiv_edges = df_indiv.groupby(['contrib_name', 'com_id']).agg(
            weight=('trans_amt', 'sum'),
            transaction_count=('trans_amt', 'count')
        ).reset_index()
        indiv_edges.columns = ['source', 'target', 'weight', 'transaction_count']
        indiv_edges['edge_type'] = 'individual_to_committee'
        edges.append(indiv_edges)

    # Edge Type B: Committee -> Candidate
    if df_com_contribs is not None and len(df_com_contribs) > 0:
        comm_edges = df_com_contribs.groupby(['com_id', 'cand_id']).agg(
            weight=('trans_amt', 'sum'),
            transaction_count=('trans_amt', 'count')
        ).reset_index()
        comm_edges.columns = ['source', 'target', 'weight', 'transaction_count']
        comm_edges['edge_type'] = 'committee_to_candidate'
        edges.append(comm_edges)

    # Edge Type C: Committee -> Candidate (Independent Expenditures)
    if df_expenditures is not None and len(df_expenditures) > 0:
        exp_edges = df_expenditures.groupby(['com_id', 'cand_id']).agg(
            weight=('trans_amt', 'sum'),
            transaction_count=('trans_amt', 'count')
        ).reset_index()
        exp_edges.columns = ['source', 'target', 'weight', 'transaction_count']
        exp_edges['edge_type'] = 'independent_expenditure'
        edges.append(exp_edges)

    if edges:
        network_edges_df = pd.concat(edges, ignore_index=True)
        network_edges_df = network_edges_df[network_edges_df['weight'] > 0]
        upload_gold_parquet(network_edges_df, "network_edges.parquet")
        
        print("📊 Building node-level network centrality lookups...")
        out_degree = network_edges_df.groupby('source')['weight'].sum().reset_index().rename(columns={'source': 'node_id', 'weight': 'total_outflow'})
        in_degree = network_edges_df.groupby('target')['weight'].sum().reset_index().rename(columns={'target': 'node_id', 'weight': 'total_inflow'})
        
        nodes_df = pd.merge(out_degree, in_degree, on='node_id', how='outer').fillna(0.0)
        upload_gold_parquet(nodes_df, "network_nodes_centrality.parquet")
    else:
        print("⚠️ No valid transaction edges generated. Skipping network exports.")

    # -------------------------------------------------------------------------
    # ANALYSIS 2: TEMPORAL SURGES & VELOCITY (Anomalous Spending Spikes)
    # -------------------------------------------------------------------------
    print("\n⏱️ Analyzing money velocity & unexpected temporal surges...")
    if df_expenditures is not None and len(df_expenditures) > 0:
        df_exp_dates = df_expenditures[df_expenditures['trans_date'].notna()].copy()
        df_exp_dates['trans_date'] = pd.to_datetime(df_exp_dates['trans_date'], errors='coerce')
        df_exp_dates = df_exp_dates.dropna(subset=['trans_date']).sort_values('trans_date')
        
        if len(df_exp_dates) > 0:
            daily_spending = df_exp_dates.groupby(['com_id', 'trans_date'])['trans_amt'].sum().reset_index()
            daily_spending['rolling_7d_avg'] = daily_spending.groupby('com_id')['trans_amt'].transform(lambda x: x.rolling(7, min_periods=1).mean())
            daily_spending['rolling_7d_std'] = daily_spending.groupby('com_id')['trans_amt'].transform(lambda x: x.rolling(7, min_periods=1).std()).fillna(0.0)
            
            daily_spending['velocity_anomaly_flag'] = np.where(
                daily_spending['trans_amt'] > (daily_spending['rolling_7d_avg'] + (2.5 * daily_spending['rolling_7d_std'])),
                1, 0
            )
            daily_spending['trans_date'] = daily_spending['trans_date'].dt.strftime('%Y-%m-%d')
            upload_gold_parquet(daily_spending, "temporal_spending_velocity.parquet")
        else:
            print("⚠️ No valid expenditure transaction dates found.")

    # -------------------------------------------------------------------------
    # ANALYSIS 3: DONOR COALITIONS / CONCENTRATION BY BUSINESS SECTOR
    # -------------------------------------------------------------------------
    print("\n🏢 Mapping donor networks and institutional concentrations...")
    if df_indiv is not None and len(df_indiv) > 0:
        donor_cohorts = df_indiv.groupby(['contrib_emp', 'com_id']).agg(
            total_funding=('trans_amt', 'sum'),
            distinct_donors=('contrib_name', 'nunique')
        ).reset_index()
        
        donor_cohorts = donor_cohorts[donor_cohorts['total_funding'] >= 5000]
        donor_cohorts = donor_cohorts.sort_values(by='total_funding', ascending=False)
        upload_gold_parquet(donor_cohorts, "donor_concentration_by_sector.parquet")

    print("\n🏁 Gold Layer Engine processing successfully concluded.")

if __name__ == "__main__":
    build_gold_layer()