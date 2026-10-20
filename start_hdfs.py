"""Start the existing Docker HDFS cluster, verify readiness, and upload the dataset."""
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args, timeout=600):
    return subprocess.run(args, cwd=ROOT, check=True, timeout=timeout)


def main():
    run('docker', 'info', '--format', '{{.ServerVersion}}', timeout=30)
    run('docker', 'compose', 'up', '-d')
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = subprocess.run(['docker', 'exec', 'namenode', 'hdfs', 'dfsadmin', '-report'],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and 'Live datanodes (1)' in result.stdout:
            safe = subprocess.run(['docker', 'exec', 'namenode', 'hdfs', 'dfsadmin', '-safemode', 'get'],
                                  capture_output=True, text=True, timeout=30)
            if safe.returncode == 0 and 'OFF' in safe.stdout:
                break
        time.sleep(3)
    else:
        raise RuntimeError('HDFS did not become ready within 120 seconds. Inspect docker compose logs.')
    source = Path(os.getenv('DATASET_PATH', str(ROOT / 'dataset/DataCoSupplyChainDataset.csv'))).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    target = os.getenv('HDFS_DATASET_PATH', '/user/logistics/project_data/DataCoSupplyChainDataset.csv')
    parent = target.rsplit('/', 1)[0]
    run('docker', 'exec', 'namenode', 'hdfs', 'dfs', '-mkdir', '-p', parent)
    run('docker', 'cp', str(source), 'namenode:/tmp/shipment-dataset.csv')
    # The host Spark client uses the published localhost DataNode port. This
    # container-side uploader must instead use the DataNode's Docker-network IP.
    run('docker', 'exec', 'namenode', 'hdfs', 'dfs', '-Ddfs.client.use.datanode.hostname=false',
        '-put', '-f', '/tmp/shipment-dataset.csv', target)
    run('docker', 'exec', 'namenode', 'hdfs', 'dfs', '-ls', target)
    print('HDFS ready and dataset uploaded. Start the backend with STORAGE_MODE=hdfs.')


if __name__ == '__main__':
    main()
