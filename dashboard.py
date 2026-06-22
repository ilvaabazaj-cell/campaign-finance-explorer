# dashboard.py
import streamlit as st
import pandas as pd
import os
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="FEC Campaign Finance Intelligence Center", layout="wide")

st.title("💵 FEC Campaign Finance Analytics Dashboard")
st.caption("Welcome to the FEC Campaign Finance Dashboard! The aim of this tool is to allow users to investigate how money moves during elections of Presidents, House and Senate members. The dashboard is entirely interactive and each tab includes a short user manual and guided interpretations for each graph.")

# --- STATE CODE TO FULL NAME MAPPER ---
STATE_MAP = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia', 'PR': 'Puerto Rico', 'VI': 'Virgin Islands'
}

# --- CENTRALIZED OPTIMIZED STORAGE INGESTION ---
GOLD_DIR = os.path.join("minio_data", "data", "gold")

@st.cache_data
def load_gold_data():
    """Loads pre-aggregated gold files into memory once to guarantee fast load times."""
    geo_df = pd.read_parquet(os.path.join(GOLD_DIR, "gold_candidate_geo_summary.parquet"))
    donor_df = pd.read_parquet(os.path.join(GOLD_DIR, "gold_donor_type_summary.parquet"))
    net_df = pd.read_parquet(os.path.join(GOLD_DIR, "gold_network_metrics.parquet"))
    
    # Map raw postal abbreviations to full names for cleaner visual rendering
    geo_df['state_full'] = geo_df['state'].map(STATE_MAP).fillna(geo_df['state'])
    return geo_df, donor_df, net_df

try:
    geo_df, donor_df, net_df = load_gold_data()
except Exception as e:
    st.error(f"❌ Could not load Gold Layer tables. Run step4_gold_layer.py first. Error: {e}")
    st.stop()

# Helper mapping for cleaner UI office display
office_mapping = {'P': 'President', 'H': 'House', 'S': 'Senate'}

# --- UPDATE SEPARATE TABS DEFINITION ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🕸️ Core Network & Anomaly Analysis",
    "⚖️ Donor Source Mix", 
    "📍 Geographic Distributions",
    "📖 Methodology"
])

# ==========================================
# TAB 1: NETWORK ANALYSIS & ADVANCED VISUALIZATIONS
# ==========================================
with tab1:
    st.header("🕸️ Deep Network Analysis & Structural Scaling")
    st.markdown("Exposing donor concentration, financial channels, inter-committee transfers, and systemic independent expenditure spikes. Select an election cycle and, optionally, a candidate to investigate how their campaigns were funded.")

    with st.expander("📖 User Guide: How to Read the Network Analysis Tab", expanded=False):
        st.info("""
        Federal campaign finance moves through distinct legal channels, which this dashboard categorizes into three primary streams:
        - **Direct Campaign Contributions (Individual to Candidate)**: Direct financial support given by an individual citizen to a candidate's official campaign committee (e.g., a citizen donating $50 online to a candidate). These are strictly capped by federal limits.  
        - **PAC-to-Candidate Contributions**: Institutional funding where a Political Action Committee (PAC) pools donations from many individuals and gives those funds directly to a candidate's campaign (e.g., an environmental or corporate PAC donating $5,000 to a supportive lawmaker).  
        - **Independent Expenditures**: Outside spending used by PACs or Super PACs to explicitly advocate for the election or defeat of a candidate—such as paying for television ads, billboards, or mailers. Crucially, by law, this money must be spent 100% independently with absolutely zero coordination or communication with the candidate’s campaign.  
        - **Inter-PAC Transfers**: Alliance-building and strategic funding pass-throughs where one Political Action Committee transfers capital directly to another PAC (e.g., a massive leadership PAC or industry coalition transferring $25,000 to a smaller, localized grassroots Super PAC to amplify their ground game). This reveals how separate political groups pool resources behind the scenes.        """)

    # Inline Filters unique to Tab 1
    c1, c2 = st.columns(2)
    with c1:
        t1_cycles = sorted(net_df['election_cycle'].unique())
        t1_selected_cycle = st.selectbox("Election cycle", t1_cycles, index=len(t1_cycles)-1, key="t1_cyc")
    
    # Filter base pool by cycle
    cycle_network = net_df[net_df['election_cycle'] == t1_selected_cycle]
    t1_candidates = sorted(cycle_network[cycle_network['source_type'] != 'Committee/PAC']['target_node'].unique())
    
    with c2:
        t1_selected_candidate = st.selectbox("Focus Profile Network (Optional)", ["All Candidates"] + t1_candidates, key="t1_cand")

    if t1_selected_candidate != "All Candidates":
        view_network = cycle_network[cycle_network['target_node'] == t1_selected_candidate]
    else:
        view_network = cycle_network

    # Metric Cards Row
    total_flow_volume = view_network['weight'].sum()
    unique_channels = len(view_network)
    avg_transaction = view_network['weight'].mean() if unique_channels > 0 else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(label="Analyzed Network Capital", value=f"${total_flow_volume:,.2f}")
    with m2:
        st.metric(label="Active Network Edges Traversed", value=f"{unique_channels:,}")
    with m3:
        st.metric(label="Mean Channel Weight", value=f"${avg_transaction:,.2f}")

    st.markdown("---")

    # --- GRAPH 1: CAPITAL FLOWS ---
    st.subheader("🏢 Primary Capital Flow Vectors")
    top_network_edges = view_network.sort_values(by='weight', ascending=False).head(15)
    
    if not top_network_edges.empty:
        fig_net_bar = px.bar(
            top_network_edges,
            x='weight',
            y='source_node',
            color='transaction_flow',
            orientation='h',
            labels={'weight': 'Total Capital Transferred ($)', 'source_node': 'Source Node'},
            title="Dense Interconnected Paths & Financial Concentrators",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_net_bar.update_layout(yaxis={'categoryorder':'total ascending'}, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_net_bar, use_container_width=True)
        
        st.caption("💡 **How to interpret:** The longest bars indicate high-concentration funding nodes. If a single PAC or individual represents a disproportionate length of the chart, the campaign network has high donor dependency rather than distributed grassroots support.")
    else:
        st.write("No major financial ties detected within this network profile threshold.")

    st.markdown("---")

    # --- GRAPHS 2 & 3: ARCHITECTURAL MIX & SURGES ---
    col_graph_left, col_graph_right = st.columns(2)
    
    with col_graph_left:
        st.subheader("🧬 Network Flow Composition")
        flow_comp = view_network.groupby('transaction_flow').agg({'weight': 'sum', 'transaction_count': 'sum'}).reset_index()
        
        fig_donut = px.pie(
            flow_comp,
            values='weight',
            names='transaction_flow',
            hole=0.4,
            title="Macro Share of Network Funds by Flow Classification",
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_donut.update_layout(legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_donut, use_container_width=True)
        
        st.caption("💡 **How to interpret:** This donut breaks down structural distribution. A high proportion of *Independent Expenditures* or *Inter-PAC Transfers* signals an ecosystem relying heavily on outside organizations and structural pass-throughs.")

    with col_graph_right:
        st.subheader("⚡ Transaction Density & Scaling Surges")
        fig_scatter = px.scatter(
            top_network_edges,
            x="transaction_count",
            y="weight",
            size="weight",
            color="transaction_flow",
            hover_name="source_node",
            title="Frequency vs Weight Network Matrix (Anomaly Exposure)",
            labels={"transaction_count": "Number of Transactions", "weight": "Total Capital ($)"},
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.caption("💡 **How to interpret:** This matrix flags anomalies. Entities in the top-left quadrant represent significant spikes—transferring massive blocks of funding over a very low number of transactions, typical of major key-event surges.")

# ==========================================
# TAB 2: DONOR SOURCE MIX
# ==========================================
with tab2:
    st.header("⚖️ Funding Composition & Individual Concentration")
    st.markdown("Examine the proportional balance between grassroots individual donors and institutional PAC action committees. To see the graphs please make a selection for each filter.")
    
    with st.expander("📖 User Guide: Funding Mix Breakdown", expanded=False):
        st.info("""
        This tab isolates and contrasts Grassroots Capital against Institutional Backing.  
        - **Individual vs. Committee Allocation**: The system filters out non-reportable entries and groups financial records by recipient candidate profiles. Direct contributions originating from private citizens are isolated and compiled to generate the Individual Funds metric, while all incoming transfers from registered Political Action Committees (PACs) are aggregated under Committee Funds.  
        - **Proportional Distribution Analysis**: By calculating the relative ratio between these two streams, the dashboard yields a candidate's dependency profile, revealing whether a campaign's momentum is driven by low-dollar individual networks or institutional political organizations.
                """)

    # Inline Filters unique to Tab 2
    c1, c2, c3 = st.columns(3)
    with c1:
        t2_cycles = sorted(donor_df['election_cycle'].unique())
        t2_selected_cycle = st.selectbox("Election Cycle", t2_cycles, index=len(t2_cycles)-1, key="t2_cyc")
    with c2:
        t2_filtered_geo = geo_df[geo_df['election_cycle'] == t2_selected_cycle]
        t2_selected_office = st.selectbox("Office", list(office_mapping.keys()), format_func=lambda x: office_mapping[x], key="t2_off")
    
    t2_filtered_geo = t2_filtered_geo[t2_filtered_geo['office_type'] == t2_selected_office]
    t2_candidates = sorted(t2_filtered_geo['cand_name'].unique())
    
    with c3:
        t2_selected_candidate = st.selectbox("Select Target Candidate", t2_candidates, key="t2_cand")

    cand_donor = donor_df[(donor_df['cand_name'] == t2_selected_candidate) & (donor_df['election_cycle'] == t2_selected_cycle)]
    t2_geo_dist = geo_df[(geo_df['cand_name'] == t2_selected_candidate) & (geo_df['election_cycle'] == t2_selected_cycle)]

    if not cand_donor.empty:
        ind_funds = cand_donor.iloc[0]['individual_funds']
        com_funds = cand_donor.iloc[0]['committee_funds']
        
        col_pie, col_bar = st.columns(2)
        with col_pie:
            breakdown_df = pd.DataFrame({
                'Source Type': ['Individual Donors', 'Political Committees (PACs)'],
                'Total Capital ($)': [ind_funds, com_funds]
            })
            fig_pie = px.pie(
                breakdown_df, 
                values='Total Capital ($)', 
                names='Source Type', 
                color_discrete_sequence=['#1d3557', '#e63946'], 
                title=f"Funding Component Mix: {t2_selected_candidate}"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            st.caption("💡 **How to interpret:** Evaluates grassroots reliance. A dominant red slice indicates strong direct individual backing, whereas a large blue slice indicates dependence on institutional committee infrastructure.")
            
        with col_bar:
            # FIXED: Using state_full and labeling it clearly as State Full Name
            fig_state_dist = px.bar(
                t2_geo_dist.sort_values(by='total_amount', ascending=False),
                x='state_full', 
                y='total_amount',
                title=f"Individual Donor Geographic Hubs for {t2_selected_candidate}",
                labels={'total_amount': 'Capital Received ($)', 'state_full': 'State Location'},
                color_discrete_sequence=['#1d3557']
            )
            st.plotly_chart(fig_state_dist, use_container_width=True)
            st.caption("💡 **How to interpret:** Pinpoints where a candidate's individual support is concentrated. Long bars show the primary geographical states providing out-of-state or local financial support.")
    else:
        st.info("ℹ️ No donor composition data discovered for this candidate selection within this timeline.")

# ==========================================
# TAB 3: GEOGRAPHIC DISTRIBUTIONS
# ==========================================
with tab3:
    st.header("📍 Geographic Contribution Inflows")
    st.markdown("Analyze where candidate fundraising originates geographically across various election timelines.")
    
    with st.expander("📖 User Guide: Map Inflow Interpretation", expanded=False):
        st.info("""
        This map visualizes the geographic concentration of individual political campaign donations across the United States using pre-computed spatial tables from the Gold Layer.  
        - **Spatial Data Normalization**: The ingestion pipeline extracts the two-letter state abbreviation reported on every individual transaction (state), filters out invalid or foreign region codes, and maps them to full regional names to build an accurate choropleth layout.  
        - **True Location Aggregation**: Financial volumes are aggregated by summing over individual contributions, grouped by the donor's state and filtered by the selected candidate's target office and election cycle. Darker shades on the map represent areas of high-density fundraising, showing you whether a candidate relies heavily on in-state constituents or successfully draws in out-of-state capital. 
                """)

    # Inline Filters unique to Tab 3
    c1, c2, c3 = st.columns(3)
    with c1:
        t3_cycles = sorted(geo_df['election_cycle'].unique())
        t3_selected_cycle = st.selectbox("Election cycle", t3_cycles, index=len(t3_cycles)-1, key="t3_cyc")
    with c2:
        t3_selected_office = st.selectbox("Office", list(office_mapping.keys()), format_func=lambda x: office_mapping[x], key="t3_off")
    
    t3_filtered = geo_df[(geo_df['election_cycle'] == t3_selected_cycle) & (geo_df['office_type'] == t3_selected_office)]
    t3_candidates = sorted(t3_filtered['cand_name'].unique())
    
    with c3:
        t3_selected_candidate = st.selectbox("Candidate Filter", ["All Candidates"] + t3_candidates, key="t3_cand")

    if t3_selected_candidate != "All Candidates":
        t3_filtered = t3_filtered[t3_filtered['cand_name'] == t3_selected_candidate]

    # Map Aggregation Engine (combines total amounts by state and includes full state names)
    map_data = t3_filtered.groupby(['state', 'state_full']).agg({'total_amount': 'sum', 'total_donations': 'sum'}).reset_index()

    col_map_left, col_map_right = st.columns([3, 1])
    with col_map_left:
        # FIXED: Added full state names to the hover info using hover_name
        fig_map = px.choropleth(
            map_data,
            locations='state',
            locationmode="USA-states",
            color='total_amount',
            scope="usa",
            hover_name='state_full',
            color_continuous_scale="Blues",
            labels={'total_amount': 'Total Raised ($)', 'state': 'Postal Code'},
            title=f"Geographic Funding Map ({t3_selected_cycle})"
        )
        st.plotly_chart(fig_map, use_container_width=True)
        st.caption("💡 **How to interpret:** Darker shades indicate states with high-volume funding concentrations. Hovering over a state displays its full name along with the total financial volume contributed to the selected pool.")

    with col_map_right:
        st.markdown("#### 🏆 Top State Inflows")
        top_states = map_data.sort_values(by='total_amount', ascending=False).head(5)
        if not top_states.empty:
            for _, row in top_states.iterrows():
                st.metric(label=row['state_full'], value=f"${row['total_amount']:,.2f}")
        else:
            st.write("No entries matching parameters.")

# ==========================================
# TAB 4: METHODOLOGY & ARCHITECTURE NOTES
# ==========================================
with tab4:
    st.header("📖 Methodological Notes")
    st.markdown("This section contains methodological notes for the content of the dashboard: data sources, metric calculation, and special cases explanations.")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.subheader("🔌 Data Provenance & Ingestion Sources")
        st.markdown(
            """
            * **2026 Election Cycle (Active Timeline):** Processed via official **FEC (Federal Election Commission) Bulk Data Download** flat files to handle high-throughput delta streams efficiently.
            * **Other Election Cycles:** Sourced programmatically via the **OpenFEC API** to extract pre-validated, archived candidate registries.
            """
        )
        
        st.subheader("📆 Temporal Constraints & Missing Profiles")
        st.write(
            "Users may notice that selecting certain years yields **no presidential candidates** "
            "in the dropdown filter. This is a deliberate, structurally accurate behavior of our dataset:"
        )
        st.warning(
            "Presidential elections are organized in a strict **4-year cycle** "
            "(e.g., 2020, 2024). Midterm cycles (e.g., 2022, 2026) only include congressional "
            "races (House and Senate). Therefore, selecting a midterm year correctly returns zero results for the executive office."
        )

        st.subheader("⏳ Chronological Data Scope: Historical & Future Dates")
        st.markdown(
            """
            When interacting with this dashboard, users may notice dates appearing in the filters that reach into the past (e.g., 1998) or extend into future election cycles (e.g., 2032). This is an intentional feature of the data design, reflecting real-world compliance logging:
            
            * **Persistent Institutional History:** Campaign committees are permanent organizations. A committee established decades ago keeps its original, unique identification number active today. Because our data lake preserves the full historical registry profile of an active committee, the system displays all previous election cycles in which that entity was legally designated to operate.
            * **Future Strategic Registrations:** Federal candidates routinely file paperwork to designate their campaigns for future re-election cycles years in advance (e.g., a Senator elected today may already have regulatory records active for their next cycle six years from now). 
            * **Real-World Compliance Typos:** This platform serves as an unfiltered transparency tool. It intentionally preserves transaction dates exactly as they were reported by committee treasurers. Minor human data-entry typos made on paper forms (such as accidentally entering a past or future year) are preserved by our pipeline rather than deleted.
            """
        )

    with col_m2:
        st.subheader("📊 Financial Aggregation & Scope")
        st.markdown(
            """
            To map the true footprint of political influence, our analytical engine groups and aggregates total dollar volumes and transaction frequencies across precise entity boundaries:
            
            * **Individual Donations:** We isolate reportable cash receipts flowing from private citizens, summing the total financial volume and counting the distinct instances of giving. These are linked directly to the donor's geographic state and grouped by the candidate's target office and election cycle.
            * **PAC & Institutional Transfers:** For committee-to-candidate interactions, we restrict our calculations to explicit, federally coded **Direct Contributions** made to candidate committees. Conversely, for outside spending, the engine isolates transactions officially logged as **Independent Expenditures** advocating for a candidate’s election or opposition.
            """
        )

        st.subheader("📝 Financial Metric Definitions & Formulas")
        st.markdown(
            """
            To ensure reporting transparency, all metrics displayed across these views are calculated using standardized financial definitions:
            
            1. **Geographic Inflows:** Represents the total net dollar volume contributed by individuals residing within a specific state. It isolates personal giving to show where a candidate's geographic donor base is concentrated.
            2. **Donor Type Breakdown:** Compares grassroots support against institutional backing by separating total funding into two categories:
               * **Individual Funds:** Direct contributions from private citizens.
               * **Committee Funds:** Transferred capital from authorized Political Action Committees (PACs).
            3. **Network Analysis Weight:** Measures the strength of financial ties between entities. The value (weight) represents the total consolidated capital flowing directly from a source node (a donor, PAC, or committee) to a target node (the candidate or recipient committee).
            """
        )

    st.markdown("---")
    st.subheader("🔍 Understanding Negative Valuation Anomalies")
    
    st.markdown(
        """
        Seeing **negative balances** (such as $-220.00$) for certain candidates, timelines, or geographic regions is a structurally accurate representation of federal election bookkeeping, rather than an error.
        
        This dashboard tracks **Net Capital Flow** rather than gross inflows. The core metric is calculated using the following financial formula:
        """
    )
    st.latex(r"\text{Net Capital Volume} = \text{Gross Incoming Contributions} - \text{Outgoing Financial Adjustments}")
    
    st.markdown(
        """
        When a campaign is highly inactive, winding down operations, or when a specific state has very little new fundraising during a selected timeframe, outgoing ledger adjustments can easily outweigh incoming active donations. This pushes the net balance below zero. 
        
        The three primary real-world drivers behind these negative adjustments are:
        * **Contribution Refunds:** The campaign legally returns money to a donor because the contribution exceeded statutory limits, came from a prohibited entity, or was formally rejected by the committee.
        * **Bounced Checks & Chargebacks:** Grassroots donations or physical checks that were voided, canceled, or disputed by financial institutions after being logged.
        * **Redesignations & Reattributions:** Accounting reallocations where money is legally backed out of one specific fund (e.g., a primary election fund that has closed) and transferred into another (e.g., a general election fund).
        """
    )