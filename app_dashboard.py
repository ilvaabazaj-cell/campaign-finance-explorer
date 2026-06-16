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

# 4. Cached Data Ingestion Helpers
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

# Load Gold Insights
df_edges = load_parquet_from_minio("gold/", "network_edges.parquet")
df_nodes = load_parquet_from_minio("gold/", "network_nodes_centrality.parquet")
df_velocity = load_parquet_from_minio("gold/", "temporal_spending_velocity.parquet")
df_sectors = load_parquet_from_minio("gold/", "donor_concentration_by_sector.parquet")

# Load Silver Metadata Tables to translate IDs back to Real Names
df_cand_master = load_parquet_from_minio("silver/", "candidate_master.parquet")
df_cmte_master = load_parquet_from_minio("silver/", "committee_master.parquet")

# Build name-to-id mapping dictionaries dynamically
cand_map = {}
if not df_cand_master.empty:
    # Ensure columns exist, standardizing to keys mapped in your Silver layer script
    c_id_col = 'cand_id' if 'cand_id' in df_cand_master.columns else 'CAND_ID'
    c_nm_col = 'cand_name' if 'cand_name' in df_cand_master.columns else 'CAND_NAME'
    if c_id_col in df_cand_master.columns and c_nm_col in df_cand_master.columns:
        cand_map = pd.Series(df_cand_master[c_id_col].values, index=df_cand_master[c_nm_col]).to_dict()

cmte_map = {}
if not df_cmte_master.empty:
    m_id_col = 'com_id' if 'com_id' in df_cmte_master.columns else 'CMTE_ID'
    m_nm_col = 'com_name' if 'com_name' in df_cmte_master.columns else 'CMTE_NM'
    if m_id_col in df_cmte_master.columns and m_nm_col in df_cmte_master.columns:
        cmte_map = pd.Series(df_cmte_master[m_id_col].values, index=df_cmte_master[m_nm_col]).to_dict()

# Reverse lookups for printing nice human-readable tables
id_to_name_map = {**{v: k for k, v in cand_map.items()}, **{v: k for k, v in cmte_map.items()}}

def translate_id(entity_id):
    """Gracefully returns the name of an ID, or the ID itself if name is missing."""
    return id_to_name_map.get(entity_id, entity_id)

# --- UI HEADER ---
st.title("🇺🇸 Campaign Capital Flow Explorer")
st.markdown("Welcome! This system tracks how money travels across American political campaigns. You don't need to know technical finance rules or tracking IDs to discover trends—use the simple controls below to audit political spending.")
st.markdown("---")

# --- GLOBAL SUMMARY STATS ---
if not df_edges.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Political Capital Tracked", f"${df_edges['weight'].sum():,.2f}", help="Total dollar value across all processed transactions.")
    with col2:
        anomalies = df_velocity['velocity_anomaly_flag'].sum() if not df_velocity.empty else 0
        st.metric("High-Risk Spending Surges Detected", f"{anomalies}", delta="Requires Review" if anomalies > 0 else "Stable")
    with col3:
        st.metric("Active Political Entities Mapped", f"{len(df_nodes):,}")

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Pipeline Flow Tracker", 
    "⏱️ High-Risk Spending Spikes", 
    "🏢 Corporate & Employer Blocs", 
    "🗺️ Geographic Money Map"
])

# =========================================================================
# TAB 1: PIPELINE FLOW TRACKER (Sankey แทน Network Graph)
# =========================================================================
with tab1:
    st.header("Money Pipeline Explorer")
    
    with st.expander("💡 How to Read This Analysis (Click to Expand)"):
        st.markdown("""
        **What is this showing?** Instead of confusing network maps, this graph shows money moving sequentially from **Senders (Left)** to **Receivers (Right)**. The thickness of each flowing band indicates the volume of cash.
        
        **How to interact:**
        1. Select a transaction type from the dropdown box.
        2. Adjust the slider to filter out minor entries and expose the dominant "mega-donors" or largest recipient pipelines.
        3. Hover your cursor over any block or stream to view exact dollar counts and transaction quantities.
        """)

    if not df_edges.empty:
        # User choices using clean labels
        raw_edge_type = st.selectbox("Select Flow Channel to Inspect", list(EDGE_TYPE_LABELS.keys()), format_func=lambda x: EDGE_TYPE_LABELS[x])
        
        # Slicing threshold
        filtered_by_type = df_edges[df_edges['edge_type'] == raw_edge_type]
        min_amt = st.slider("Filter out transactions below this amount ($)", 
                            float(filtered_by_type['weight'].min()), 
                            float(filtered_by_type['weight'].quantile(0.99) if len(filtered_by_type) > 100 else filtered_by_type['weight'].max()), 
                            float(filtered_by_type['weight'].median()))
        
        plot_df = filtered_by_type[filtered_by_type['weight'] >= min_amt].copy()
        
        if not plot_df.empty:
            # Humanize IDs to Names for Display Node Blocks
            plot_df['source_name'] = plot_df['source'].apply(translate_id)
            plot_df['target_name'] = plot_df['target'].apply(translate_id)
            
            # Construct distinct list of unique names indexed for Plotly's Sankey engine
            all_nodes = list(set(plot_df['source_name']).union(set(plot_df['target_name'])))
            node_indices = {name: i for i, name in enumerate(all_nodes)}
            
            # Map sources/targets to integer indices
            source_indices = plot_df['source_name'].map(node_indices).tolist()
            target_indices = plot_df['target_name'].map(node_indices).tolist()
            weights = plot_df['weight'].tolist()
            
            # Build the Sankey Flow Graph Object
            fig_sankey = go.Figure(data=[go.Sankey(
                node = dict(
                  pad = 15, thickness = 20,
                  line = dict(color = "black", width = 0.5),
                  label = all_nodes,
                  color = "#3182bd"
                ),
                link = dict(
                  source = source_indices,
                  target = target_indices,
                  value = weights,
                  hovertemplate = 'Source: %{source.label}<br />Target: %{target.label}<br />Total Money Transferred: $% {value:,.2f}<extra></extra>'
              ))])
            
            fig_sankey.update_layout(title_text="Orderly Breakdown of Capital Pipelines", font_size=11, height=600)
            st.plotly_chart(fig_sankey, use_container_width=True)
        else:
            st.warning("No financial streams matched this filter threshold. Lower the slider value.")

# =========================================================================
# TAB 2: HIGH-RISK SPENDING SPIKES
# =========================================================================
with tab2:
    st.header("Anomalous Spending Velocity Tracker")
    
    with st.expander("💡 How to Read This Analysis (Click to Expand)"):
        st.markdown("""
        **What is this showing?** Political campaigns usually spend money at a steady, predictable pace. This tool monitors spending timelines and flags **abnormal spikes** where spending suddenly leaps more than 2.5 standard deviations above its 7-day average baseline.
        
        **Why does it matter?** Massive, uncharacteristic flash-spending events near voting deadlines often indicate last-minute negative ad campaigns or hidden defense strategies.
        
        **How to interact:** Select a political committee from the list (sorted alphabetically by their official organization name). If a red warning triggers, review the log table below the graph to inspect the spike date.
        """)

    if not df_velocity.empty and cmte_map:
        # Filter down velocity items to committees whose names are mapped in our lookup system
        df_velocity['cmte_name'] = df_velocity['com_id'].apply(translate_id)
        available_cmtes = sorted(df_velocity['cmte_name'].unique())
        
        selected_cmte_name = st.selectbox("Choose a Committee Name to Audit", available_cmtes)
        selected_cmte_id = cmte_map.get(selected_cmte_name, selected_cmte_name)
        
        com_timeline = df_velocity[df_velocity['com_id'] == selected_cmte_id].sort_values('trans_date')
        
        if not com_timeline.empty:
            fig_time = px.line(com_timeline, x="trans_date", y="trans_amt", 
                               title=f"Daily spending trajectory for: {selected_cmte_name}",
                               labels={"trans_date": "Date of Operation", "trans_amt": "Cash Spent ($)"},
                               template="plotly_white", line_shape="linear")
            
            # Isolate the data entries carrying the anomaly warning flag
            flags = com_timeline[com_timeline['velocity_anomaly_flag'] == 1]
            if not flags.empty:
                st.error(f"🚨 FRAUD/RISK DETECTOR: {selected_cmte_name} triggered {len(flags)} unusual flash-spending spikes!")
                
                # Overlay bright red alert triangles on top of our timeline
                fig_time.add_scatter(x=flags['trans_date'], y=flags['trans_amt'],
                                     mode='markers', marker=dict(color='red', size=12, symbol='triangle-up'),
                                     name='Statistically Abnormal Surge')
                
                # Show explicit clean table
                st.dataframe(flags[['trans_date', 'trans_amt', 'rolling_7d_avg']].rename(
                    columns={'trans_date': 'Spike Date', 'trans_amt': 'Abnormal Amount Spent', 'rolling_7d_avg': 'Normal 7-Day Baseline Avg'}
                ), use_container_width=True)
            else:
                st.success("✅ Clean Record: This committee's spending patterns conform entirely to normal baselines.")
                
            st.plotly_chart(fig_time, use_container_width=True)

# =========================================================================
# TAB 3: CORPORATE & EMPLOYER BLOCS
# =========================================================================
with tab3:
    st.header("Employer Funding Coalitions")
    
    with st.expander("💡 How to Read This Analysis (Click to Expand)"):
        st.markdown("""
        **What is this showing?** By law, individual donors must declare their employer. This chart stacks individual contributions together by **Employer Name** to highlight coordinated financial support bases.
        
        **Why does it matter?** If a massive cluster of donations originates from executives or employees at a single corporate entity or tech company, it signals an institutional funding bloc.
        """)

    if not df_sectors.empty:
        df_sectors_clean = df_sectors.copy()
        df_sectors_clean['Target Committee Name'] = df_sectors_clean['com_id'].apply(translate_id)
        
        # Clean up missing or unprovided text values
        df_sectors_clean['contrib_emp'] = df_sectors_clean['contrib_emp'].replace(['None', 'nan', ''], 'NOT SPECIFIED')
        
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
            st.dataframe(df_sectors_clean[['contrib_emp', 'Target Committee Name', 'total_funding', 'distinct_donors']].rename(
                columns={'contrib_emp': 'Funder Employer', 'total_funding': 'Total Funds', 'distinct_donors': 'Unique Core Donors'}
            ), use_container_width=True, height=380, hide_index=True)

# =========================================================================
# TAB 4: GEOGRAPHIC MONEY MAP
# =========================================================================
with tab4:
    st.header("Geographic Campaign Capital Breakdown")
    
    with st.expander("💡 How to Read This Analysis (Click to Expand)"):
        st.markdown("""
        **What is this showing?** This interactive US map charts **where political action committees are physically located and spending money from**. 
        
        **Why does it matter?** Elections are local, but campaign finance is national. This view helps you track if local campaigns are powered by home-state citizens or financed by political committees located in remote capital hubs (like Washington D.C., Virginia, or California).
        
        **How to interact:** Hover over any state to reveal total active capital outflows coming out of that state's boundaries.
        """)

    # We map spending concentrations by looking at the official state locations of committees 
    # that are generating independent expenditures or direct candidate disbursements.
    df_silver_exp = load_parquet_from_minio("silver/", "independent_expenditures.parquet")
    df_silver_cmte = load_parquet_from_minio("silver/", "committee_master.parquet")
    
    if not df_silver_exp.empty and not df_silver_cmte.empty:
        # Standardize join keys
        exp_com_col = 'com_id' if 'com_id' in df_silver_exp.columns else 'CMTE_ID'
        exp_amt_col = 'trans_amt' if 'trans_amt' in df_silver_exp.columns else 'TRANSACTION_AMT'
        
        cmte_id_col = 'com_id' if 'com_id' in df_silver_cmte.columns else 'CMTE_ID'
        cmte_st_col = 'com_state' if 'com_state' in df_silver_cmte.columns else 'CMTE_ST'
        
        # Clean data type configurations
        df_silver_exp[exp_amt_col] = pd.to_numeric(df_silver_exp[exp_amt_col], errors='coerce').fillna(0.0)
        df_silver_cmte[cmte_st_col] = df_silver_cmte[cmte_st_col].astype(str).str.upper().str.strip()
        
        # Link records together to inherit geographic attributes
        geo_spend = pd.merge(df_silver_exp, df_silver_cmte[[cmte_id_col, cmte_st_col]], left_on=exp_com_col, right_on=cmte_id_col, how='inner')
        
        # Group together state totals
        state_totals = geo_spend.groupby(cmte_st_col)[exp_amt_col].sum().reset_index()
        state_totals.columns = ['state_code', 'total_expenditures']
        
        # Filter down data framework to legitimate 50 US State postal abbreviations
        us_states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
                     "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
                     "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY", "DC"]
        state_totals = state_totals[state_totals['state_code'].isin(us_states)]
        
        if not state_totals.empty:
            # Build Choropleth Graph Map Object
            fig_map = px.choropleth(
                state_totals,
                locations='state_code',
                locationmode="USA-states",
                color='total_expenditures',
                scope="usa",
                color_continuous_scale="Reds",
                labels={'total_expenditures': 'Total Capital Expended ($)'},
                title="Total Campaign Capital Outflow Distribution by State"
            )
            
            fig_map.update_layout(
                geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='rgb(255, 255, 255)'),
                height=600
            )
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("Insufficient structured geo-location elements found in current sample dataset to display map data.")
    else:
        st.info("Ingest bulk files containing committee location states to initialize the geospatial map module.")