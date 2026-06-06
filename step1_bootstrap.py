import os
import tempfile
import pandas as pd
from minio import Minio
from minio.error import S3Error

def main():
    # 1. Connect to the local MinIO container
    print("Connecting to MinIO container...")
    client = Minio(
        "127.0.0.1:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    bucket_name = "data"

    # 2. Automatically create the bucket if it's missing
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"✅ Created bucket: '{bucket_name}'")
        else:
            print(f"ℹ️ Bucket '{bucket_name}' already exists.")
    except S3Error as e:
        print(f"❌ Error initializing bucket: {e}")
        return

    # 3. Define mapping of the sample files to upload and process
    fec_files = {
        "cn_sample.txt": "cn_header_file.csv",
        "cm_sample.txt": "cm_header_file.csv"
    }

    local_seed_dir = "data_seed"

    # 4. Upload local seed files to the raw/ partition of MinIO
    print("\n🚀 Uploading sample seed files to raw/ prefix...")
    for data_file, header_file in fec_files.items():
        try:
            # Upload data file
            client.fput_object(bucket_name, f"raw/{data_file}", os.path.join(local_seed_dir, data_file))
            print(f"   Caricato grezzo: raw/{data_file}")
            
            # Upload header file
            if header_file:
                client.fput_object(bucket_name, f"raw/{header_file}", os.path.join(local_seed_dir, header_file))
                print(f"   Caricato header: raw/{header_file}")
        except Exception as e:
            print(f"   ❌ Errore caricamento seed {data_file}: {e}")
            return

    print("\n--- INIZIO PIPELINE BRONZE (RAW -> PARQUET) ---")

    # 5. Download back from raw/, merge headers, and upload to bronze/
    with tempfile.TemporaryDirectory() as temp_dir:
        for data_file, header_file in fec_files.items():
            print(f"\n⚙️ Processando: {data_file}...")
            
            try:
                local_data_path = os.path.join(temp_dir, data_file)
                
                # Download data from the raw lake location
                client.fget_object(bucket_name, f"raw/{data_file}", local_data_path)
                
                columns = None
                if header_file:
                    local_header_path = os.path.join(temp_dir, header_file)
                    client.fget_object(bucket_name, f"raw/{header_file}", local_header_path)
                    
                    # Read only the columns header line
                    header_df = pd.read_csv(local_header_path, nrows=0)
                    columns = header_df.columns.tolist()

                # Process safely using the memory-safe C engine configuration
                df = pd.read_csv(
                    local_data_path, 
                    sep="|", 
                    names=columns, 
                    dtype=str, 
                    on_bad_lines="skip",
                    engine="c"
                )

                # Convert to Parquet file structure
                parquet_filename = data_file.replace(".txt", ".parquet")
                local_parquet_path = os.path.join(temp_dir, parquet_filename)
                
                print(f"   Conversione in Parquet ({len(df)} righe elaborate)...")
                df.to_parquet(local_parquet_path, engine="pyarrow", compression="snappy")

                # Upload to the Bronze zone of MinIO
                minio_bronze_path = f"bronze/{parquet_filename}"
                client.fput_object(bucket_name, minio_bronze_path, local_parquet_path)
                
                print(f"   ✅ BRONZE LAYER COMPLETATO: {bucket_name}/{minio_bronze_path}")

            except Exception as e:
                print(f"   ❌ ERRORE in elaborazione {data_file}: {e}")

    print("\n--- PIPELINE BRONZE COMPLETATA CON SUCCESSO ---")

if __name__ == "__main__":
    main()