To get the local data lake infrastructure, MinIO, and the ingestion pipelines running on your machine, please follow these steps in order.

**Prerequisite Checklist (Install these first)**
- Git: If you don't have it, download and install it from git-scm.com.
- Docker Desktop: Download and install it from docker.com. (Make sure Docker Desktop is open and running before proceeding!)
- Python 3.11, 3.12, or 3.13: Ensure Python is installed on your machine.

**Step 1: Clone the Repository**
Open your terminal (or Command Prompt) inside the folder where you want to keep university projects, and run:

_git clone https://github.com/ilvaabazaj-cell/campaign-finance-explorer.git
cd campaign-finance-explorer_

Open this cloned folder in Visual Studio Code.

**Step 2: Create a Local Virtual Environment**
Open the internal terminal in VS Code and run these commands to set up an isolated workspace and install all project dependencies:

On Windows:

_python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt_

On Mac/Linux:

_python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt_

**Step 3: Create Your Private Configuration File (.env)**
Because we use a .gitignore file to protect secret keys, our private configurations are not uploaded to GitHub. You need to create this file locally.

Create a new file in the root folder of the project named exactly .env (make sure it doesn't end in .txt!).

Paste the following configuration inside it:

MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=access key
MINIO_SECRET_KEY=password
OPENFEC_API_KEY=use the API key you got from OpenFEC API

**Step 4: Boot Up the MinIO Storage Infrastructure**
Make sure Docker Desktop is open in the background. In your VS Code terminal, run:

_docker compose up -d_

Verification Check: Open your browser and go to http://localhost:9001. Log in using the username and password for MinIO we put in the .env file. You will see an empty data lake bucket ready to go!

**Step 5: Run the Pipelines**
Now you can execute the exact scripts to seed historical data and fetch live nightly updates directly into your local storage container:

Seed the Historical Bronze Data:

_python step1_bootstrap.py_

(This creates the data/ bucket in MinIO, parses the raw bulk text files from data_seed/, and uploads them as high-performance Parquet files into the Bronze layer!)

Fetch the Live OpenFEC API Updates:

_python step2_api_ingest.py_

(This contacts the live OpenFEC API, securely processes pages of raw JSON data using your .env key, and stores the incremental nightly data into your MinIO storage.)

Process and Standardize the Silver Layer:

_python step3_silver_layer.py_

(This runs the data cleaning and standardization pipeline using a native MinIO client. It automatically matches raw data sources, converts fields names, standardizes all date fields to the ISO format YYYY-MM-DD, drops transaction duplicates based on sub_id, and outputs optimized, uniform consolidated files into the silver/ directory.)


**Before closing the computer**
Whenever you are done working for the day, you can turn off the storage containers by running docker compose down in your terminal so it doesn't use your laptop's battery or RAM in the background! Everything will be perfectly saved for next time.
