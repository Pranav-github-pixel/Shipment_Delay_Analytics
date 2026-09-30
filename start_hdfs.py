import os
import subprocess
import time

def main():
    print("Starting HDFS cluster via Docker Compose...")
    try:
        # Check if docker-compose exists
        subprocess.run(["docker-compose", "up", "-d"], check=True)
    except Exception as e:
        print(f"Error starting docker-compose: {e}")
        print("Please ensure Docker Desktop is installed and running, and docker-compose is in your PATH.")
        return

    print("Waiting for HDFS Namenode to become ready on port 9000 (usually takes 20-30 seconds)...")
    time.sleep(30)
    
    print("HDFS cluster is running!")
    print("Namenode UI: http://localhost:9870")
    
    # Check if we need to put the dataset in HDFS
    dataset_path = "dataset/DataCoSupplyChainDataset.csv"
    if os.path.exists(dataset_path):
        print("\nFound dataset locally. You can upload it to HDFS using the following command:")
        print("docker exec -it namenode bash -c \"hdfs dfs -mkdir -p /user/logistics/project_data\"")
        # To copy from host to docker container:
        print("docker cp dataset/DataCoSupplyChainDataset.csv namenode:/tmp/")
        print("docker exec -it namenode bash -c \"hdfs dfs -put /tmp/DataCoSupplyChainDataset.csv /user/logistics/project_data/\"")
    else:
        print(f"Notice: local dataset not found at {dataset_path}. If you want to use HDFS, please place it there and upload.")

if __name__ == "__main__":
    main()
