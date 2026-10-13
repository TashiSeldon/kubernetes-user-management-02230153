# Run this in a PowerShell window before starting the hey load test.
# It samples HPA CPU and replica counts every 30 seconds and writes a CSV file.
$ErrorActionPreference = 'Stop'
$namespace = 'usermgmt-02230153'
$outputFile = Join-Path $PSScriptRoot 'hpa-timeline.csv'

'Time,CurrentCPUPercent,CurrentReplicas,DesiredReplicas,ReadyAPIPods' |
    Set-Content -Path $outputFile -Encoding UTF8

Write-Host "Recording every 30 seconds to $outputFile"
Write-Host 'Press Ctrl+C after the load ends and you have recorded several cooldown minutes.'

while ($true) {
    $hpa = kubectl get hpa api -n $namespace -o json | ConvertFrom-Json
    $deployment = kubectl get deployment api -n $namespace -o json | ConvertFrom-Json
    $cpu = $hpa.status.currentMetrics[0].resource.current.averageUtilization
    $current = $hpa.status.currentReplicas
    $desired = $hpa.status.desiredReplicas
    $ready = $deployment.status.readyReplicas
    $time = Get-Date -Format 'HH:mm:ss'
    $line = "$time,$cpu,$current,$desired,$ready"
    Write-Host $line
    Add-Content -Path $outputFile -Value $line -Encoding UTF8
    Start-Sleep -Seconds 30
}
