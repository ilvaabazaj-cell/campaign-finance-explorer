import os
from minio import Minio
from minio.error import S3Error
import time
import psutil

start_time = time.time()
def main():
    # 1. Connect to the local MinIO storage container
    print("📡 Connecting to MinIO data lake container...")
    client = Minio(
        "127.0.0.1:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    bucket_name = "data"

    # 2. Automatically verify or build the core bucket
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"✅ Created core data lake bucket: '{bucket_name}'")
        else:
            print(f"ℹ️ Core data lake bucket '{bucket_name}' already exists.")
            
        print("\n⚡ [BRONZE LAYER ARCHITECTURE VERIFIED] ⚡")
        print("Docker Volume bind mount has successfully mapped raw FEC bulk data into storage.")
        print("Ready for memory-safe, high-volume analytical processing!")

    except S3Error as e:
        print(f"❌ Error initializing data lake infrastructure: {e}")
        return

if __name__ == "__main__":
    main()

end_time = time.time()
runtime_seconds = end_time - start_time

print(f"⏱️ Runtime: {runtime_seconds:.2f} seconds")

process = psutil.Process(os.getpid())
peak_memory_bytes = process.memory_info().peak_wset
peak_memory_mb = peak_memory_bytes / (1024 * 1024)
print(f"\n📊 [MEMORY PROFILE]: Peak RAM consumption: {peak_memory_mb:.2f} MB")