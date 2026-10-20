param([ValidateSet('local','hdfs')][string]$Mode='local', [int]$Port=8000)
$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
# Spark 3.5's Windows batch launcher requires TEMP without spaces.
# Keep the Windows default; Spark's larger scratch files use SPARK_LOCAL_DIR.
if ($env:TEMP -match '\s') { throw 'Spark 3.5 on Windows requires TEMP and TMP to point to a writable path without spaces.' }
if (-not $env:JAVA_HOME) {
    $localJdk = Get-ChildItem -LiteralPath (Join-Path $projectRoot '.runtime') -Directory -Filter 'jdk-17*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($localJdk) { $env:JAVA_HOME = $localJdk.FullName }
}
if ($env:JAVA_HOME) { $env:PATH = (Join-Path $env:JAVA_HOME 'bin') + ';' + $env:PATH }
if (-not (Get-Command java -ErrorAction SilentlyContinue)) { throw 'Java not found. Install Java 17 and set JAVA_HOME.' }
if (-not $env:HADOOP_HOME -and (Test-Path '.hadoop/bin/winutils.exe')) { $env:HADOOP_HOME = Join-Path $projectRoot '.hadoop' }
if ($env:HADOOP_HOME) { $env:PATH = (Join-Path $env:HADOOP_HOME 'bin') + ';' + $env:PATH }
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $pythonPath)) { throw 'Create .venv and install requirements.txt first (see context.md).' }
$env:PYSPARK_PYTHON = $pythonPath
$env:STORAGE_MODE = $Mode
& $pythonPath -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port $Port
