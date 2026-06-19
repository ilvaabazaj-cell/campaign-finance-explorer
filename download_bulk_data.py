import os
import gdown

def download_fec_data():
    # 1. Target directory matching our Docker Bind Mount path
    target_dir = os.path.join("minio_data", "data", "bronze")
    
    # Ensure the folder structure exists locally
    os.makedirs(target_dir, exist_ok=True)
    
    # 2. Your dynamic dictionary mapping target files to Google Drive IDs
    # TODO: Replace these placeholders with your actual Google Drive File IDs!
    fec_files = {
        "cm.txt": "1qf_3iKWolGnfPJTsa9nN8x2d2vNEltQg",
        "cn.txt": "1s0FIIg5QD6lX2Qmn2nzcImDLeNmicoR5", 
        "itcont.txt": "1319MOWoiT0ZPh6DPiptosbDl5wAma_Vi", 
        "itoth.txt": "1cq3qHXnY__aNjNIZOeddKCt8s5DAxx9o",
        "itpas2.txt": "1RZhIAHuW48iuJr96iMKv47_U8-gx0I9F"
    }
    
    print("⏳ Starting automated download of heavy FEC bulk datasets from Google Drive...")
    print(f"📁 Destination: ./{target_dir}/\n")
    
    for filename, file_id in fec_files.items():
        output_path = os.path.join(target_dir, filename)
        
        # If the file is already sitting there locally from a previous run, skip it!
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"✅ {filename} already exists locally. Skipping download.")
            continue
            
        print(f"📥 Fetching {filename} from secure cloud storage...")
        
        # Formulate the Google Drive clean direct-download endpoint URL
        url = f"https://drive.google.com/uc?id={file_id}"
        
        try:
            # gdown handles large files and Google Drive's virus scan warning screens automatically
            gdown.download(url, output_path, quiet=False)
            print(f"✨ Successfully saved {filename} to {output_path}\n")
        except Exception as e:
            print(f"❌ Critical Error downloading {filename}: {e}")

if __name__ == "__main__":
    download_fec_data()