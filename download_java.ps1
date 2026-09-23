$url = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jre_x64_windows_hotspot_17.0.10_7.zip"
$zipFile = "jre-17.zip"
$extractPath = "jre"

Write-Host "Downloading JRE..."
Invoke-WebRequest -Uri $url -OutFile $zipFile
Write-Host "Extracting JRE..."
Expand-Archive -Path $zipFile -DestinationPath $extractPath -Force
Write-Host "JRE Extraction Complete!"
