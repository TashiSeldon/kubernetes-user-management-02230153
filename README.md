# Kubernetes user management assignment

Student number: **02230153**  
Namespace: `usermgmt-02230153`  
Ingress host: `usermgmt-02230153.local`

This repository implements the assignment with a Flask REST API and PostgreSQL. The numbered `k8s/` manifests are applied in order. Keep actual credentials in `k8s/01-secrets.yaml`; that file is ignored by Git. The supplied `01-secrets.example.yaml` contains a placeholder and must not be applied unchanged.

Clone the project before following the deployment steps:

```powershell
git clone https://github.com/TashiSeldon/kubernetes-user-management-02230153.git
Set-Location .\kubernetes-user-management-02230153
```

The repository is private unless its owner changes visibility or grants the assessor access.

## Prerequisites and platform

Use Docker Desktop, minikube, kubectl, git, and (for load testing) `hey`. On Windows, run the VPA installation script from WSL 2 or Git Bash. Start the cluster and enable platform add-ons:

```bash
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube addons enable ingress
kubectl get storageclass
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
git fetch --depth=1 origin tag vertical-pod-autoscaler-1.8.0
MSYS2_ARG_CONV_EXCL=/CN= ./hack/vpa-up.sh
cd <your-repository>
```

The manifests assume the minikube Ingress NGINX add-on (`ingressClassName: nginx`). For Windows/Docker Desktop keep `minikube tunnel` running in another elevated terminal and add `127.0.0.1 usermgmt-02230153.local` to `C:\Windows\System32\drivers\etc\hosts`. Linux uses the address from `minikube ip` instead. If you choose Traefik, change the Ingress class and state that choice in the report.

## Build and deploy

From the repository root:

```bash
cp k8s/01-secrets.example.yaml k8s/01-secrets.yaml
# Edit k8s/01-secrets.yaml and set a unique POSTGRES_PASSWORD.
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-postgres.yaml
kubectl rollout status statefulset/postgres -n usermgmt-02230153
docker build -t usermgmt-api:1.0 ./app
minikube image load usermgmt-api:1.0
kubectl apply -f k8s/03-api.yaml
kubectl rollout status deployment/api -n usermgmt-02230153
kubectl apply -f k8s/04-ingress.yaml
kubectl apply -f k8s/05-hpa.yaml
kubectl apply -f k8s/06-vpa.yaml
```

If using PowerShell, replace `cp` with `Copy-Item`. The assignment requires all application objects to be created from YAML. The `kubectl apply` commands above satisfy that rule; use `kubectl` imperatively for inspection and the required Pod-deletion persistence test only.

### Windows PowerShell deployment commands

Run these commands from the repository root after starting Minikube and installing VPA from Git Bash. Keep the actual Secret local and replace the placeholder password before applying it.

```powershell
kubectl config use-context minikube
if (-not (Test-Path .\k8s\01-secrets.yaml)) {
    Copy-Item .\k8s\01-secrets.example.yaml .\k8s\01-secrets.yaml
} else {
    Write-Host 'Keeping the existing local Secret file; edit it only if required.'
}
notepad .\k8s\01-secrets.yaml

kubectl apply -f .\k8s\00-namespace.yaml
kubectl apply -f .\k8s\01-secrets.yaml
kubectl apply -f .\k8s\02-postgres.yaml
kubectl rollout status statefulset/postgres -n usermgmt-02230153 --timeout=180s
kubectl get statefulset,pod,pvc,pv -n usermgmt-02230153

docker build -t usermgmt-api:1.0 .\app
minikube image load usermgmt-api:1.0
kubectl apply -f .\k8s\03-api.yaml
kubectl rollout status deployment/api -n usermgmt-02230153 --timeout=180s
kubectl apply -f .\k8s\04-ingress.yaml
kubectl apply -f .\k8s\05-hpa.yaml
kubectl apply -f .\k8s\06-vpa.yaml
kubectl get deploy,rs,pods,svc,hpa,vpa -n usermgmt-02230153
```

If the API Deployment already exists after rebuilding the image, run `kubectl rollout restart deployment/api -n usermgmt-02230153` and wait for its rollout. Do not delete the namespace or PVC for routine updates; namespace deletion removes the database claim and its data.

### Windows Ingress access

Add `127.0.0.1 usermgmt-02230153.local` to the Windows hosts file as Administrator. Keep this command running in its own PowerShell window. Port `8086` was verified for the Ingress controller. Use `8087` for the API Service port-forward if ports `8080` through `8085` are occupied:

```powershell
kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 8086:80
```

Verify access and host-based routing in another window:

```powershell
curl.exe -i http://usermgmt-02230153.local:8086/users
curl.exe -i -H "Host: other.local" http://127.0.0.1:8086/users
kubectl describe ingress api -n usermgmt-02230153
```

The configured host should reach the API; the unmatched host should not return the application user list.

## Verify CRUD

Start a local port-forward in one terminal:

```bash
kubectl port-forward -n usermgmt-02230153 svc/api 8087:80
```

In another terminal, run each command and save the real output for the report:

```bash
curl -i http://localhost:8087/healthz
curl -i http://localhost:8087/ready
curl -i -X POST http://localhost:8087/users -H 'Content-Type: application/json' -d '{"name":"Student 02230153","email":"student02230153@example.test"}'
curl -i http://localhost:8087/users
curl -i http://localhost:8087/users/1
curl -i -X PUT http://localhost:8087/users/1 -H 'Content-Type: application/json' -d '{"name":"Updated Student 02230153","email":"updated02230153@example.test"}'
curl -i -X DELETE http://localhost:8087/users/1
curl -i http://localhost:8087/users/1
```

The generated user ID may not be `1` if you have already created records. Read the ID returned by POST and substitute that value in subsequent requests. In PowerShell, `Invoke-RestMethod` is also suitable for the CRUD calls. The final GET should return 404 after successful deletion.

Check PostgreSQL readiness and current resource use with:

```powershell
kubectl exec postgres-0 -n usermgmt-02230153 -- sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
kubectl top pods -n usermgmt-02230153
kubectl get statefulset,pod,pvc,pv -n usermgmt-02230153
```

PowerShell example using the API port-forward above:

```powershell
$baseUrl = 'http://localhost:8087'
$email = "student02230153-$([guid]::NewGuid().ToString('N'))@example.test"
$body = @{ name = 'Student 02230153'; email = $email } | ConvertTo-Json
$created = Invoke-RestMethod -Uri "$baseUrl/users" -Method Post -ContentType 'application/json' -Body $body
$id = $created.id
$created
Invoke-RestMethod -Uri "$baseUrl/users" -Method Get
Invoke-RestMethod -Uri "$baseUrl/users/$id" -Method Get

$update = @{ name = 'Updated Student 02230153'; email = "updated-$email" } | ConvertTo-Json
Invoke-RestMethod -Uri "$baseUrl/users/$id" -Method Put -ContentType 'application/json' -Body $update
Invoke-RestMethod -Uri "$baseUrl/users/$id" -Method Delete
try {
    Invoke-RestMethod -Uri "$baseUrl/users/$id" -Method Get
} catch {
    $_.Exception.Response.StatusCode.value__  # Expected: 404
}
```

## Persistence test

Use the API to insert a record, then delete only the database Pod (not its PVC). Keep the port-forward from the CRUD section running:

```bash
curl -i -X POST http://localhost:8087/users -H 'Content-Type: application/json' -d '{"name":"Persistence Test","email":"persist02230153@example.test"}'
curl -s http://localhost:8087/users
kubectl delete pod postgres-0 -n usermgmt-02230153
kubectl wait --for=condition=Ready pod/postgres-0 -n usermgmt-02230153 --timeout=180s
curl -s http://localhost:8087/users
```

Capture the before, deletion/recreation, and after outputs. PostgreSQL's StatefulSet reuses its claim, so the row remains on the persistent volume.

PowerShell version (uses a new email so it does not overwrite an existing record):

```powershell
$baseUrl = 'http://localhost:8087'
$email = "persist02230153-$([guid]::NewGuid().ToString('N'))@example.test"
$body = @{ name = 'Persistence Test 02230153'; email = $email } | ConvertTo-Json
$record = Invoke-RestMethod -Uri "$baseUrl/users" -Method Post -ContentType 'application/json' -Body $body
$record
kubectl delete pod postgres-0 -n usermgmt-02230153
kubectl wait --for=condition=Ready pod/postgres-0 -n usermgmt-02230153 --timeout=180s
Invoke-RestMethod -Uri "$baseUrl/users" -Method Get | Where-Object email -eq $email
```

This deletes only the Pod. Do not delete the PVC or namespace for this test.

## Ingress test

```bash
curl -i http://usermgmt-02230153.local:8086/users
curl -i -H 'Host: other.local' http://127.0.0.1:8086/users
kubectl describe ingress api -n usermgmt-02230153
```

The wrong-host request should not return the application's user list. Depending on the controller it may return its default backend response or 404. The route is client → ingress controller → matching host/path rule → `api` Service → ready API Pod.

## Autoscaling evidence

```bash
kubectl top nodes
kubectl top pods -n usermgmt-02230153
kubectl get hpa api -n usermgmt-02230153 -w
kubectl describe vpa postgres -n usermgmt-02230153
```

In another terminal, generate traffic against the Ingress host for three minutes, for example:

```bash
hey -z 3m -c 50 http://usermgmt-02230153.local:8086/users
```

Record HPA desired/current replicas and API Pod count every 30 seconds during load and for several minutes afterward. Do not claim scale-up or scale-down unless your observed output shows it. In a separate terminal run `kubectl describe vpa postgres -n usermgmt-02230153` after the load and copy the recommendation values into the report. VPA `Off` reports recommendations without changing database requests. The HPA uses CPU utilization of the API, while VPA observes PostgreSQL, so they do not control the same workload. An HPA and VPA changing CPU requests on the same API Deployment can counteract each other because CPU utilization is calculated relative to requests.

On Windows, run `monitor-hpa.ps1` in its own PowerShell window before `hey`. It verifies the Minikube context and writes samples to a new timestamped `hpa-timeline-<date-time>.csv` file so earlier evidence is not overwritten. Keep the Ingress port-forward running in a separate window. A moderate test is `& "$env:TEMP\hey.exe" -z 30s -c 10 http://usermgmt-02230153.local:8086/users`; use the assignment's `-z 3m -c 50` only when the cluster is stable and report any HTTP errors and timeouts accurately. Keep sampling for several cooldown minutes; if six replicas remain at the last sample, report that scale-down was not captured rather than claiming it occurred.

## Troubleshooting and final checks

Capture one actual issue you encounter and diagnose it using evidence, for example:

```bash
kubectl describe pod <pod-name> -n usermgmt-02230153
kubectl logs <pod-name> -n usermgmt-02230153
kubectl get events -n usermgmt-02230153 --sort-by=.lastTimestamp
kubectl get endpointslices -n usermgmt-02230153 -l kubernetes.io/service-name=api -o wide
kubectl logs -n usermgmt-02230153 -l app=api --all-containers=true --since=10m --prefix
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --since=10m
```

Explain the actual symptom, the relevant event/log line, your fix, and the result. Do not present a hypothetical failure as something that happened.

Do not delete the namespace or PVC as a troubleshooting step. The PVC is the persistent database volume. If a clean reset is required, first export or back up the records and explicitly decide that the database contents may be discarded.
