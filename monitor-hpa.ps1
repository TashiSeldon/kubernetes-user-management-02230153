# Run this in a PowerShell window before starting the hey load test.
# It samples HPA CPU and replica counts every 30 seconds and writes a CSV file.
$ErrorActionPreference = 'Stop'
$namespace = 'usermgmt-02230153'
$fileStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputFile = Join-Path $PSScriptRoot "hpa-timeline-$fileStamp.csv"

$context = kubectl config current-context 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Could not read the current kubectl context. Check your kubeconfig.'
}
if ($context -ne 'minikube') {
    throw "Current kubectl context is '$context'. Run 'kubectl config use-context minikube' and try again."
}
$namespaceResult = kubectl get namespace $namespace --ignore-not-found -o name 2>$null
if ($LASTEXITCODE -ne 0 -or -not $namespaceResult) {
    throw "Namespace '$namespace' was not found in the minikube context. Start minikube and apply k8s/00-namespace.yaml."
}

'Time,CurrentCPUPercent,CurrentReplicas,DesiredReplicas,ReadyAPIPods' |
    Set-Content -Path $outputFile -Encoding UTF8

Write-Host "Recording every 30 seconds to $outputFile"
Write-Host 'Press Ctrl+C after the load ends and you have recorded several cooldown minutes.'

while ($true) {
    try {
        $hpaJson = kubectl get hpa api -n $namespace -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Unable to read the HPA.' }
        $hpa = $hpaJson | ConvertFrom-Json

        $deploymentJson = kubectl get deployment api -n $namespace -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Unable to read the API Deployment.' }
        $deployment = $deploymentJson | ConvertFrom-Json

        $cpu = 'N/A'
        foreach ($metric in @($hpa.status.currentMetrics)) {
            if ($metric.type -eq 'Resource' -and $metric.resource.name -eq 'cpu' -and
                $null -ne $metric.resource.current.averageUtilization) {
                $cpu = $metric.resource.current.averageUtilization
                break
            }
        }
        $current = if ($null -ne $hpa.status.currentReplicas) { $hpa.status.currentReplicas } else { 'N/A' }
        $desired = if ($null -ne $hpa.status.desiredReplicas) { $hpa.status.desiredReplicas } else { 'N/A' }
        $ready = if ($null -ne $deployment.status.readyReplicas) { $deployment.status.readyReplicas } else { 0 }
    }
    catch {
        Write-Warning "Could not collect this sample: $($_.Exception.Message)"
        Start-Sleep -Seconds 30
        continue
    }

    $time = Get-Date -Format 'HH:mm:ss'
    $line = "$time,$cpu,$current,$desired,$ready"
    Write-Host $line
    Add-Content -Path $outputFile -Value $line -Encoding UTF8
    Start-Sleep -Seconds 30
}
