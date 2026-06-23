# USA Campaign Finance & Donor Network Transparency Explorer

An end-to-end **Medallion Architecture Data Lake** built to ingest, clean, aggregate, and visualize U.S. Federal Election Commission (FEC) campaign finance records. This system handles high-volume, multi-structured records (historical flat-files and live REST API endpoints) using a completely modern, serverless data stack: **MinIO** as an object store container, **DuckDB** as an out-of-core vectorized analytical engine, and **Streamlit** for interactive dashboarding.

---

## 💾 System Requirements & Storage Footprint

> ⚠️ **IMPORTANT NOTE ON DISK SPACE:** Because this project processes real-world, high-throughput federal campaign finance data, it requires a baseline allocation of local storage to function correctly.
> * **Bulk File Ingestion Footprint:** The raw historical FEC text files downloaded during the bootstrap phase collectively weigh approximately **5.5 GB** on your local machine.
> * **Pipeline Handling:** These raw files must live temporarily in your local storage workspace before they are programmatically parsed, schema-aligned, and uploaded into the containerized MinIO object store.
> * **Hardware Recommendation:** Please ensure you have at least **12 GB–15 GB of free disk space** available on your host machine before running the ingestion engine to allow comfortable headroom for the raw data, Docker volumes, and final compressed Parquet outputs.
> 
> 

---

## 📋 Prerequisites

Ensure you have the following tools installed on your host machine:

1. **Docker Desktop** (with Docker Compose support)
2. **Python 3.11+**
3. **An OpenFEC API Key** (You can sign up instantly for an official government developer key at [api.open.fec.gov](https://api.open.fec.gov))

---

## 🚀 Step-by-Step Setup and Execution

Follow these steps in exact chronological order to configure the environment, run the extraction pipelines, build the analytics layer, and launch the user interface.

### Step 1: Clone the Repository and Set Up Environment Variables

Execute the following commands in your terminal to clone the project tree and enter the working directory:

```bash
git clone https://github.com/ilvaabazaj-cell/campaign-finance-explorer.git
cd campaign-finance-explorer

```

Next, create a file named `.env` in the root directory of the project and populate it with your environment credentials:

```env
# OpenFEC API Key Configuration
OPENFEC_API_KEY=YOUR_ACTUAL_FEC_API_KEY_HERE

# MinIO Local Storage Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

```

*(Note: A template structure of this file can be referenced inside `.env.example` in the repository.)*

### Step 2: Initialize and activate a Virtual Envirorment

It is highly recommended to isolate your project dependencies using a Python virtual environment to avoid conflicts with global packages.

```bash
# Create the virtual environment
python -m venv venv

# Activate on Windows:
.\\venv\\Scripts\\activate

# OR Activate on macOS/Linux:
source venv/bin/activate

```
*(Note: Once successfully activated, your terminal prompt will display a (venv) prefix.)

### Step 3: Install Python Dependencies

Install the required packages using pip:

```bash
pip install -r requirements.txt

```

### Step 4: Boot the Object Storage Infrastructure (Docker)

Spin up the local containerized MinIO server in detached mode:

```bash
docker compose up -d

```

*Note: You can inspect your active data lake buckets via the browser UI at [http://localhost:9001](http://localhost:9001) using the credentials `minioadmin` / `minioadmin`.*

---

## ⚙️ Pipeline Deep Dive: Step-by-Step Execution

### Step 5: Run the Ingestion Pipelines (Bronze Stage)

This stage initializes our raw object storage environment and executes our dual-mode extraction strategies (combining historical block downloads with real-time API polling).

```bash
# A. Download historical bulk datasets via gdown
python download_bulk_data.py

```

* **Technical Breakdown:** This script targets the raw baseline data of the project. It interfaces with Google Drive via the `gdown` engine to programmatically fetch the massive, static historical FEC blocks (Committee Master, Candidate Master, Individual Contributions, Inter-PAC Transfers, and PAC-to-Candidate tables). To protect your system bandwidth, it features an **idempotency filter**: it checks if a file is already present on disk with a size greater than zero; if so, it skips the network call completely.


```bash
# B. Create the infrastructure directories and data lake buckets
python step1_bootstrap.py

```

* **Technical Breakdown:** This script communicates with your Dockerized MinIO container via the Python MinIO Client API. It verifies whether your centralized storage bucket (`"data"`) exists, creating it dynamically if missing. By utilizing Docker volume binds mapped from `minio_data/data` on your host machine into the container's virtual path, this initialization ensures that any files processed locally immediately sync as persistent cloud objects.







```bash
# C. Pull real-time active transactional payloads from the OpenFEC REST API
python step2_api_ingest.py

```

* **Technical Breakdown:** This handles our live data velocity. It queries the official federal endpoints for real-time campaign updates. It is built with high infrastructure resilience: it incorporates exception-catching loops to handle 502/504 network drops, pausing for 5 seconds before retrying up to 3 times. To prevent breaking API rate limits during grading, a pagination guard rail restricts ingestion to the top 5 pages per endpoint. Data rows are flattened into dataframes, forced into un-nested string schemas to prevent casting exceptions, and written to `bronze/incoming_api/` as Snappy-compressed Parquet files.

---

### Step 6: Execute Schema Unification and Data Cleansing (Silver Stage)

This step takes the multi-structured, disparate raw inputs and prepares them for formal database querying.

```bash
# Run the schema unification and cleaning task
python step3_silver_layer.py

```

* **Technical Breakdown:** The bulk files have zero header records, while the API outputs nested JSON blocks. This script utilizes an explicit column dictionary registry (`MAPPINGS` and `HEADER_MAPS`) to enforce a single database schema. Using DuckDB's fast thread-pooling features (`parallel=True`), it streams the raw inputs, applies a comprehensive `UNION ALL` statement across the bulk views and active API dataframes, and processes them through an extensive cleanup block:
* **Dates:** Standardizes variations into clear `YYYY-MM-DD` timestamp strings.
* **Casting:** Converts raw financial fields into high-precision floating numbers (`DOUBLE`), setting empty fields to `0.0`.
* **Text Scrubbing:** Trims whitespace padding, sets keys to uppercase, and provides fallback strings (like `'NOT SPECIFIED'`) for missing company names.
* **Deduplication:** Runs an out-of-core `SELECT DISTINCT` query over the entire cleaned data stack, streaming duplicates directly to disk without overloading your machine's RAM, before saving the output to the `silver/` path.



---

### Step 7: Generate Specialized Analytical Tables (Gold Stage)

This step converts our cleaned historical rows into pre-computed data structures configured specifically for dashboard rendering.

```bash
# Pre-calculate analytical summaries and multi-channel networks
python step4_gold_layer.py

```

* **Technical Breakdown:** Rather than running slow database aggregates on the fly when the dashboard page loads, this script pre-calculates your analytical tables ahead of time. It loads DuckDB's virtual network file extension (`httpfs`), allowing it to run lightning-fast SQL queries directly against compressed Parquet files stored inside MinIO over HTTP.


* It runs an advanced regex-split function (`regexp_split_to_table`) to break down candidates' comma-separated multi-year election cycle arrays into discrete database records.


* It computes regional fundraising totals grouped by candidate and state for mapping.


* It generates a unified financial matrix by executing a four-path network flow query (unifying Individual-to-Candidate, PAC-to-Candidate, Inter-PAC, and Independent Expenditures), outputting pre-calculated summary aggregates straight into the `data/gold/` target path.





---

### Step 8: Launch the Campaign Finance Explorer Dashboard

With all the computational heavy lifting safely handled by your data lake pipeline, launch the user interface:

```bash
streamlit run dashboard.py

```

Once initialized, open your web browser and navigate to the local interface address:
👉 **[http://localhost:8501](http://localhost:8501)**

* **Technical Design Breakdown:** By keeping your application stack serverless, you do not need heavy database server containers running. DuckDB runs embedded inside the application process itself. The user interface leverages Streamlit's `@st.cache_data` optimization decorator. This caches the pre-computed Gold tables into local memory on launch, ensuring that adjustments to your dropdown menus and map filters render instantly without triggering slow, repetitive file scans.



---

### 🛑 Graceful Shutdown & Teardown

Once you are finished exploring the data and wish to close the environment, follow these steps to securely shut down the architecture and free up system resources:

1. Stop the Dashboard: In the terminal running Streamlit, press Ctrl + C to terminate the user interface process.

2. Spin Down the Data Lake: Shut down the MinIO container and remove the active Docker network:

```bash
docker compose down

```

3. Deactivate the Virtual Environment: Exit your isolated Python workspace to return to your global system environment:

```bash
deactivate

```
* **Technical Design Breakdown:** Running `docker compose down` gracefully stops the active container but safely preserves your MinIO configurations and processed database files physically mapped to your host machine's `minio_data` folder. You can safely boot the system back up anytime without losing your Gold layer aggregations!
