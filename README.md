# Kubernetes user management assignment

Student number: **02230153**  
Namespace: `usermgmt-02230153`  
Ingress host: `usermgmt-02230153.local`

This starter implements the assignment with a Flask REST API and PostgreSQL. The numbered `k8s/` manifests are applied in order. Keep actual credentials in `k8s/01-secrets.yaml`; that file is ignored by Git. The supplied `01-secrets.example.yaml` contains a placeholder and must not be applied unchanged.

## Prerequisites and platform

Use Docker Desktop, minikube, kubectl, git, and (for load testing) `hey`. On Windows, run the VPA installation script from WSL 2 or Git Bash. Start the cluster and enable platform add-ons:

```bash
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube addons enable ingress
kubectl get storageclass
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
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

## Verify CRUD

Start a local port-forward in one terminal:

```bash
kubectl port-forward -n usermgmt-02230153 svc/api 8080:80
```

In another terminal, run each command and save the real output for the report:

```bash
curl -i http://localhost:8080/healthz
curl -i http://localhost:8080/ready
curl -i -X POST http://localhost:8080/users -H 'Content-Type: application/json' -d '{"name":"Student 02230153","email":"student02230153@example.test"}'
curl -i http://localhost:8080/users
curl -i http://localhost:8080/users/1
curl -i -X PUT http://localhost:8080/users/1 -H 'Content-Type: application/json' -d '{"name":"Updated Student 02230153","email":"updated02230153@example.test"}'
curl -i -X DELETE http://localhost:8080/users/1
curl -i http://localhost:8080/users/1
```

The generated user ID may not be `1` if you have already created records. Read the ID returned by POST and substitute that value in subsequent requests. The final GET should return 404 after successful deletion.

## Persistence test

Use the API to insert a record, then delete only the database Pod (not its PVC). Keep the port-forward from the CRUD section running:

```bash
curl -i -X POST http://localhost:8080/users -H 'Content-Type: application/json' -d '{"name":"Persistence Test","email":"persist02230153@example.test"}'
curl -s http://localhost:8080/users
kubectl delete pod postgres-0 -n usermgmt-02230153
kubectl wait --for=condition=Ready pod/postgres-0 -n usermgmt-02230153 --timeout=180s
curl -s http://localhost:8080/users
```

Capture the before, deletion/recreation, and after outputs. PostgreSQL's StatefulSet reuses its claim, so the row remains on the persistent volume.

## Ingress test

```bash
curl -i http://usermgmt-02230153.local/users
curl -i -H 'Host: other.local' http://127.0.0.1/users
kubectl describe ingress api -n usermgmt-02230153
```

The wrong-host request should not return the application's user list. Depending on the controller it may return its default backend response or 404. The route is client → ingress controller → matching host/path rule → `api` Service → ready API Pod.

## Autoscaling evidence

```bash
kubectl top nodes
kubectl top pods -n usermgmt-02230153
kubectl get hpa -n usermgmt-02230153 -w
```

In another terminal, generate traffic against the Ingress host for three minutes, for example:

```bash
hey -z 3m -c 50 http://usermgmt-02230153.local/users
```

Record HPA desired/current replicas and API Pod count every 30 seconds during load and for several minutes afterward. Do not claim scale-up or scale-down unless your observed output shows it. In a separate terminal run `kubectl describe vpa postgres -n usermgmt-02230153` after the load and copy the recommendation values into the report. VPA `Off` reports recommendations without changing database requests. The HPA uses CPU utilization of the API, while VPA observes PostgreSQL, so they do not control the same workload. An HPA and VPA changing CPU requests on the same API Deployment can counteract each other because CPU utilization is calculated relative to requests.

## Troubleshooting and final checks

Capture one actual issue you encounter and diagnose it using evidence, for example:

```bash
kubectl describe pod <pod-name> -n usermgmt-02230153
kubectl logs <pod-name> -n usermgmt-02230153
kubectl get events -n usermgmt-02230153 --sort-by=.lastTimestamp
```

Explain the actual symptom, the relevant event/log line, your fix, and the result. Do not present a hypothetical failure as something that happened.

Before submission, remove and redeploy the namespace as the assignment asks. Preserve only the intended application data; namespace deletion removes its claims/data.
