import os
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from minio import Minio

# 1. Page Configuration Setup
st.set_page_config(page_title="US Election Money Tracker", layout="wide", page_icon="🇺🇸")

# 2. Establish MinIO Connection
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
host_endpoint = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")

minio_client = Minio(
    host_endpoint,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)
BUCKET_NAME = "data"

# 3. Clean Display Dictionaries for Datasets
EDGE_TYPE_LABELS = {
    "individual_to_committee": "Individual Donors to Political Committees (PACs)",
    "committee_to_candidate": "Direct Committee Contributions to Candidates",
    "independent_expenditure": "PAC Independent Spending (Advertisements/Support)"
}

# 4. Cached Data Ingestion Helpers (Optimized)
@st.cache_data
def load_parquet_from_minio(prefix, filename):
    """Streams a Parquet file from a given prefix directory in MinIO into memory."""
    try:
        response = minio_client.get_object(BUCKET_NAME, f"{prefix}{filename}")
        data_bytes = response.read()
        response.close()
        response.release_conn()
        return pd.read_parquet(io.BytesIO(data_bytes))
    except Exception:
        return pd.DataFrame()

# Load Masters first to build lightning fast index mapping series
df_cand_master = load_parquet_from_minio("silver/candidate_master/", "candidate_master_clean.parquet")
df_cmte_master = load_parquet_from_minio("silver/committee_master/", "committee_master_clean.parquet")

# Build lightning fast vector maps
# Build lightning fast vector maps (Deduplicated to prevent InvalidIndexError)
id_to_name_series = pd.Series(dtype='str')

if not df_cand_master.empty:
    # Ensure unique mappings by dropping duplicate IDs
    df_cand_clean_mapping = df_cand_master.drop_duplicates(subset=['cand_id'])
    cand_series = pd.Series(df_cand_clean_mapping['cand_name'].values, index=df_cand_clean_mapping['cand_id'])
    id_to_name_series = pd.concat([id_to_name_series, cand_series])

if not df_cmte_master.empty:
    # Ensure unique mappings by dropping duplicate IDs
    df_cmte_clean_mapping = df_cmte_master.drop_duplicates(subset=['com_id'])
    cmte_series = pd.Series(df_cmte_clean_mapping['com_name'].values, index=df_cmte_clean_mapping['com_id'])
    # Combine them, keeping the first instance if a candidate and committee share an ID
    id_to_name_series = id_to_name_series.combine_first(cmte_series)

# Final safety check: remove any unexpected duplicate indices that survived the merge
id_to_name_series = id_to_name_series[~id_to_name_series.index.duplicated(keep='first')]

# Pre-load core metrics frameworks
df_edges = load_parquet_from_minio("gold/", "network_edges.parquet")
df_velocity = load_parquet_from_minio("gold/", "temporal_spending_velocity.parquet")
df_sectors = load_parquet_from_minio("gold/", "donor_concentration_by_sector.parquet")

# Map names using native vectorized mappings (100x faster than .apply loops)
if not df_edges.empty:
    df_edges['source_name'] = df_edges['source'].map(id_to_name_series).fillna(df_edges['source'])
    df_edges['target_name'] = df_edges['target'].map(id_to_name_series).fillna(df_edges['target'])

# --- UI HEADER ---
st.title("🇺🇸 Campaign Capital Flow Explorer")
st.markdown("Select a target candidate or committee in the sidebar to dynamically generate targeted insights without slowing down your browser.")
st.markdown("---")

# --- GLOBAL SIDEBAR FILTERING (MANDATORY ENTITY SELECTION) ---
st.sidebar.header("🔍 Targeted Capital Auditor")

if not df_edges.empty:
    # Gather distinct names that actually have transaction records
    all_known_names = sorted(list(set(df_edges['source_name'].dropna()).union(set(df_edges['target_name'].dropna()))))
    
    # Force user to pick an entity - No massive global defaults
    filter_name = st.sidebar.selectbox("Select Target Entity to Audit", all_known_names, index=0)
else:
    st.sidebar.error("No transactional network data found in Gold layer.")
    st.stop()

# --- DYNAMIC SUMMARY STATS FOR SELECTED ENTITY ---
entity_edges = df_edges[(df_edges['source_name'] == filter_name) | (df_edges['target_name'] == filter_name)]
total_capital = entity_edges['weight'].sum()

col1, col2 = st.columns(2)
with col1:
    st.metric(f"Total Tracked Volume for Selected Entity", f"${total_capital:,.2f}")
with col2:
    st.metric("Associated Connections", f"{len(entity_edges)}")

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Pipeline Flow Tracker", 
    "⏱️ High-Risk Spending Spikes", 
    "🏢 Corporate & Employer Blocs", 
    "🗺️ Geographic Money Map"
])

# =========================================================================
# TAB 1: PIPELINE FLOW TRACKER (Sankey Graph Engine - Capped at Top 20)
# =========================================================================
with tab1:
    st.header(f"Flow Networks for: {filter_name}")
    
    raw_edge_type = st.selectbox("Select Flow Channel to Inspect", list(EDGE_TYPE_LABELS.keys()), format_func=lambda x: EDGE_TYPE_LABELS[x])
    filtered_by_type = entity_edges[entity_edges['edge_type'] == raw_edge_type]
    
    if not filtered_by_type.empty:
        # Sort and isolate only the Top 20 records to keep rendering instant
        plot_df = filtered_by_type.sort_values(by='weight', ascending=False).head(20).copy()
        st.caption(f"Showing the top {len(plot_df)} largest financial connections to prevent canvas freezing.")
        
        all_nodes = list(set(plot_df['source_name']).union(set(plot_df['target_name'])))
        node_indices = {name: i for i, name in enumerate(all_nodes)}
        
        source_indices = plot_df['source_name'].map(node_indices).tolist()
        target_indices = plot_df['target_name'].map(node_indices).tolist()
        weights = plot_df['weight'].tolist()
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 15, thickness = 20,
              line = dict(color = "black", width = 0.5),
              label = all_nodes,
              color = "#1f77b4"
            ),
            link = dict(
              source = source_indices,
              target = target_indices,
              value = weights,
              hovertemplate = 'Source: %{source.label}<br />Target: %{target.label}<br />Total Transferred: $% {value:,.2f}<extra></extra>'
          ))])
        
        fig_sankey.update_layout(font_size=11, height=500)
        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.warning(f"No connections found for '{filter_name}' under this specific flow channel.")

# =========================================================================
# TAB 2: HIGH-RISK SPENDING SPIKES
# =========================================================================
with tab2:
    st.header("Anomalous Spending Velocity Tracker")
    
    if not df_velocity.empty:
        # Vectorized translation for quick lookup
        df_velocity['cmte_name'] = df_velocity['com_id'].map(id_to_name_series).fillna(df_velocity['com_id'])
        
        # Check if the chosen entity is a committee in this table
        com_timeline = df_velocity[df_velocity['cmte_name'] == filter_name].sort_values('trans_date')
        
        if not com_timeline.empty:
            fig_time = px.line(com_timeline, x="trans_date", y="daily_amt" if "daily_amt" in com_timeline.columns else "trans_amt", 
                               title=f"Daily spending trajectory for: {filter_name}",
                               labels={"trans_date": "Date of Operation", "trans_amt": "Cash Spent ($)", "daily_amt": "Cash Spent ($)"},
                               template="plotly_white")
            
            flags = com_timeline[com_timeline['velocity_anomaly_flag'] == 1]
            if not flags.empty:
                st.error(f"🚨 FRAUD/RISK DETECTOR: {filter_name} triggered {len(flags)} unusual flash-spending spikes!")
                fig_time.add_scatter(x=flags['trans_date'], y=flags['daily_amt'] if "daily_amt" in flags.columns else flags['trans_amt'],
                                     mode='markers', marker=dict(color='red', size=12, symbol='triangle-up'),
                                     name='Statistically Abnormal Surge')
                
                st.dataframe(flags[['trans_date', 'daily_amt', 'rolling_7d_avg']].rename(
                    columns={'trans_date': 'Spike Date', 'daily_amt': 'Abnormal Amount Spent', 'rolling_7d_avg': 'Normal 7-Day Baseline Avg'}
                ), use_container_width=True)
            else:
                st.success("✅ Clean Record: This committee's spending patterns conform entirely to normal baselines.")
                
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.info("The selected entity is either a candidate or has no documented daily timeline records.")

# =========================================================================
# TAB 3: CORPORATE & EMPLOYER BLOCS
# =========================================================================
with tab3:
    st.header("Employer Funding Coalitions")

    if not df_sectors.empty:
        df_sectors_clean = df_sectors.copy()
        df_sectors_clean['Target Committee Name'] = df_sectors_clean['com_id'].map(id_to_name_series).fillna(df_sectors_clean['com_id'])
        df_sectors_clean['contrib_emp'] = df_sectors_clean['contrib_emp'].replace(['None', 'nan', ''], 'NOT SPECIFIED')
        
        # Isolate to selected committee
        df_sectors_clean = df_sectors_clean[df_sectors_clean['Target Committee Name'] == filter_name]
        
        if not df_sectors_clean.empty:
            top_blocs = df_sectors_clean.groupby('contrib_emp')['total_funding'].sum().reset_index()
            top_blocs = top_blocs[top_blocs['contrib_emp'] != 'NOT SPECIFIED'].sort_values('total_funding', ascending=False).head(10)
            
            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                st.markdown("**Top 10 Most Powerful Employer Blocs ($)**")
                fig_blocs = px.bar(top_blocs, x='total_funding', y='contrib_emp', orientation='h',
                                   labels={'total_funding': 'Total Capital Contributed ($)', 'contrib_emp': 'Donor Employer'},
                                   color='total_funding', color_continuous_scale='teal', template='plotly_white')
                fig_blocs.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
                st.plotly_chart(fig_blocs, use_container_width=True)
                
            with col_b2:
                st.markdown("**Complete Donor Cohort Ledger**")
                st.dataframe(df_sectors_clean[['contrib_emp', 'total_funding', 'distinct_donors']].rename(
                    columns={'contrib_emp': 'Funder Employer', 'total_funding': 'Total Funds', 'distinct_donors': 'Unique Core Donors'}
                ), use_container_width=True, height=380, hide_index=True)
        else:
            st.warning("No sector employment mappings listed for this specific group.")

# =========================================================================
# TAB 4: GEOGRAPHIC MONEY MAP
# =========================================================================
with tab4:
    st.header("Geographic Campaign Capital Breakdown")

    df_silver_exp = load_parquet_from_minio("silver/independent_expenditures/", "independent_expenditures_clean.parquet")
    df_silver_cmte = load_parquet_from_minio("silver/committee_master/", "committee_master_clean.parquet")
    
    if not df_silver_exp.empty and not df_silver_cmte.empty:
        exp_com_col = 'com_id' if 'com_id' in df_silver_exp.columns else 'CMTE_ID'
        exp_amt_col = 'trans_amt' if 'trans_amt' in df_silver_exp.columns else 'TRANSACTION_AMT'
        
        cmte_id_col = 'com_id' if 'com_id' in df_silver_cmte.columns else 'CMTE_ID'
        cmte_st_col = 'com_state' if 'com_state' in df_silver_cmte.columns else 'CMTE_ST'
        
        df_silver_exp[exp_amt_col] = pd.to_numeric(df_silver_exp[exp_amt_col], errors='coerce').fillna(0.0)
        df_silver_cmte[cmte_st_col] = df_silver_cmte[cmte_st_col].astype(str).str.upper().str.strip()
        
        # Filter down records to just our selected committee before running the merge join
        df_silver_cmte['com_name'] = df_silver_cmte[cmte_id_col].map(id_to_name_series).fillna(df_silver_cmte[cmte_id_col])
        selected_cmte_ids = df_silver_cmte[df_silver_cmte['com_name'] == filter_name][cmte_id_col].unique()
        
        df_exp_filtered = df_silver_exp[df_silver_exp[exp_com_col].isin(selected_cmte_ids)]
        
        if not df_exp_filtered.empty:
            geo_spend = pd.merge(df_exp_filtered, df_silver_cmte[[cmte_id_col, cmte_st_col]], left_on=exp_com_col, right_on=cmte_id_col, how='inner')
            state_totals = geo_spend.groupby(cmte_st_col)[exp_amt_col].sum().reset_index()
            state_totals.columns = ['state_code', 'total_expenditures']
            
            us_states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
                         "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
                         "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY", "DC"]
            state_totals = state_totals[state_totals['state_code'].isin(us_states)]
            
            if not state_totals.empty:
                fig_map = px.choropleth(
                    state_totals,
                    locations='state_code',
                    locationmode="USA-states",
                    color='total_expenditures',
                    scope="usa",
                    color_continuous_scale="Reds",
                    labels={'total_expenditures': 'Total Capital Expended ($)'},
                    title=f"Campaign Spending Outflow Origin Map for: {filter_name}"
                )
                fig_map.update_layout(
                    geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='rgb(255, 255, 255)'),
                    height=500
                )
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.info("No expenditures matched legitimate state postal codes.")
        else:
            st.info("No recorded spatial expenditure actions exist for this selected entity.")
    else:
        st.info("Geospatial infrastructure indexes are loading...")