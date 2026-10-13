# Deploying a Scalable User Management Application on Kubernetes

**Student number:** 02230153  
**Namespace:** `usermgmt-02230153`  
**Ingress host:** `usermgmt-02230153.local`  
**Cluster/controller:** Minikube v1.39.0 with the NGINX Ingress add-on  
**Date:** [date of lab]

> Replace every bracketed prompt with your own observed result. Insert the screenshots listed below from your own machine. Do not report the example outcome as measured evidence.

## 1. Aim and architecture

This lab deploys a small user management API on a local Kubernetes cluster. The API supports create, list, read, update, and delete operations backed by PostgreSQL. A StatefulSet and persistent volume claim preserve database files across Pod replacement. A ClusterIP Service provides stable in-cluster access, and an Ingress routes the personal host name to the API. Metrics Server supplies resource metrics; an HPA scales API replicas, while a VPA in recommendation-only mode observes PostgreSQL.

**Figure 1. Architecture of the user management service.** Draw or insert a diagram showing: browser/curl → Ingress controller → Ingress rule for `usermgmt-02230153.local` → `api` Service → two or more API Pods → `postgres` headless Service → `postgres-0` StatefulSet Pod → PVC/PV. Show ConfigMap and Secret inputs to the API and database. Label the HPA targeting Deployment `api` and VPA (`Off`) targeting StatefulSet `postgres`.

## 2. Cluster and platform setup

The cluster was started with two CPUs and 4 GiB memory. I enabled the NGINX Ingress controller and metrics-server, installed the three VPA components, and created namespace `usermgmt-02230153` from `00-namespace.yaml`. The default StorageClass is `standard`, using provisioner `k8s.io/minikube-hostpath`. The node was Ready on Kubernetes v1.37.0. Metrics were available: `kubectl top nodes` reported 604m CPU (7%) and 1054Mi memory (13%). The ingress controller, metrics-server, and all three VPA Pods were Running.

**Figure 2. Cluster nodes and metrics.** Screenshot `kubectl get nodes` and `kubectl top nodes` with the terminal command and output visible.

**Figure 3. VPA components.** Screenshot `kubectl get pods -n kube-system | grep vpa` showing the recommender, updater, and admission controller each `1/1 Running`.

## 3. Stateful database

PostgreSQL runs as a one-replica StatefulSet. The headless Service provides stable DNS, and `volumeClaimTemplates` provisions a 1 GiB claim from the default StorageClass. Database name, user, and password are read from `postgres-secret`; credentials are not embedded in the StatefulSet. The API also reads its database password from this Secret. Requests and limits are configured for the database container.

**Figure 4. Database resources and bound storage.** Screenshot `kubectl get statefulset,pod,pvc,pv -n usermgmt-02230153` showing `postgres-0` Ready and the 1 GiB claim Bound to StorageClass `standard`.

**Figure 5. Database persistence test.** Show a row selected before Pod deletion, the `kubectl delete pod postgres-0` and successful wait/recreation output, then the same row selected after recreation. Include the actual command results, not just the commands.

## 4. API deployment and CRUD verification

The Flask API stores user records in PostgreSQL. The ConfigMap supplies non-secret connection settings and the Secret supplies the password. The Deployment requests and limits CPU/memory, runs two replicas, and defines liveness (`/healthz`) and readiness (`/ready`) probes. Readiness checks PostgreSQL so a Pod is removed from Service endpoints when the database is unavailable. The `api` ClusterIP Service sends traffic to the API Pods.

**Figure 6. API Kubernetes resources.** Screenshot `kubectl get deploy,rs,pods,svc -n usermgmt-02230153` after the rollout is complete.

**Figure 7. CRUD endpoint test.** Screenshot terminal output from the port-forward and successful POST, list, GET-by-ID, PUT, and DELETE requests. Include the final GET showing the deleted record is absent (404). Use an ID returned by your own POST response.

The API uses parameterized SQL for user input. The `users.email` column has a unique constraint, so duplicate email creation/update returns HTTP 409. Missing required fields return 400 and an unknown ID returns 404.

## 5. Ingress routing

The Ingress uses class `[nginx or traefik]` and matches host `usermgmt-02230153.local` with the `/` prefix, forwarding to Service `api` on port 80. The hosts file maps the name to `[127.0.0.1 with minikube tunnel / minikube IP]`. A different host does not match the rule and returns [observed status/body].

**Figure 8. Ingress configuration and host routing.** Include `kubectl describe ingress -n usermgmt-02230153`, the hosts-file entry, successful `curl http://usermgmt-02230153.local/users`, and a request to another host with its observed response.

Request path: the client resolves the host to the local cluster entry point; the Ingress controller receives the HTTP request and evaluates the Ingress host/path rule; it forwards to Service `api`; the Service selects ready Pods labelled `app: api` and routes to their container port 5000.

## 6. Horizontal and vertical autoscaling

Metrics-server returned API Pod metrics through `kubectl top pods`. The HPA uses `autoscaling/v2`, targets Deployment `api`, has minimum 2 and maximum 6 replicas, and targets average CPU utilization of 50%. I generated load with [tool and exact command] and recorded the current/desired replicas every 30 seconds.

| Elapsed time | Load state | HPA current/desired replicas | API Pods ready | CPU utilization |
|---|---|---:|---:|---:|
| 00:00 | Before load | [ ] | [ ] | [ ] |
| 00:30 | Load | [ ] | [ ] | [ ] |
| 01:00 | Load | [ ] | [ ] | [ ] |
| 01:30 | Load | [ ] | [ ] | [ ] |
| 02:00 | Load | [ ] | [ ] | [ ] |
| 02:30 | Load | [ ] | [ ] | [ ] |
| 03:00 | Load ends | [ ] | [ ] | [ ] |
| 04:00 | Cooldown | [ ] | [ ] | [ ] |
| 05:00 | Cooldown | [ ] | [ ] | [ ] |

The three-minute load run lasted 181.9 seconds at 50 concurrent workers. `hey` reported 7,408 HTTP 200 responses, six HTTP 500 responses, and one HTTP 502 response, with 40.76 requests per second. API logs for the HTTP 500 responses showed `psycopg2.OperationalError` because the API could not resolve the database Service hostname `postgres` for a short period. The log establishes a transient DNS lookup failure; it does not establish the underlying DNS cause. The single HTTP 502 was observed in `hey`, but the API logs do not identify its cause.

| Time | CPU utilization | HPA current/desired replicas | Ready API Pods | Phase |
|---|---:|---:|---:|---|
| 08:03:24 | 3% | 2/2 | 2 | Before load |
| 08:04:57 | 94% | 2/4 | 2 | Load |
| 08:05:27 | 94% | 4/4 | 4 | Load |
| 08:05:58 | 158% | 4/6 | 4 | Load |
| 08:06:30 | 158% | 6/6 | 6 | Load |
| 08:07:31 | 92% | 6/6 | 6 | Load |
| 08:08:32 | 48% | 6/6 | 6 | Load ended/cooldown |
| 08:09:34 | 2% | 6/6 | 6 | Cooldown |
| 08:13:38 | 2% | 6/6 | 6 | Cooldown |
| 08:14:08 | 2% | 2/2 | 2 | Cooldown, scaled down |
| 08:15:10 | 2% | 2/2 | 2 | Cooldown |

**Figure 9. Pod resource metrics.** Screenshot `kubectl top pods -n usermgmt-02230153` showing API and PostgreSQL metrics.

**Figure 10. HPA response to load.** Screenshot the 30-second monitor output showing scale-up from 2 to 6 replicas and cooldown back to 2. Include the `hey` summary and status-code distribution; report the seven non-200 responses accurately.

VPA `postgres` targets the database StatefulSet with `updateMode: Off`. After the load, it reported CPU recommendations of 33m lower bound, 63m target, and 9044m upper bound. Memory recommendations were 250Mi lower bound and target, and 1,486,217,943 bytes (about 1.38 GiB) upper bound. It reports recommendations without changing requests or restarting the database Pod. I attached VPA to PostgreSQL because the HPA manages API CPU scale-out; separating the targets prevents HPA and VPA from reacting to changing CPU requests on the same workload. On the API, raising CPU requests would reduce measured CPU utilization as a percentage of requests and could cause the HPA to scale down while VPA is scaling requests upward. The database is stateful, so recommendation-only mode let me inspect sizing suggestions without automatic changes.

**Figure 11. VPA database recommendations.** Screenshot `kubectl describe vpa postgres -n usermgmt-02230153` after the load test, with target/lower/upper recommendations visible.

## 7. Troubleshooting

**Problem observed:** The VPA admission controller did not start because its TLS Secret was missing.  
**Diagnosis:** The first `./hack/vpa-up.sh` attempt failed during certificate generation: Git Bash rewrote the OpenSSL subject `/CN=vpa_webhook_ca` as a Windows path. `kubectl describe pod ... -n kube-system` showed `FailedMount` for missing Secret `vpa-tls-certs`.  
**Fix and verification:** I used `MSYS2_ARG_CONV_EXCL=/CN= ./hack/vpa-up.sh` so Git Bash would preserve the certificate subject while still converting file paths. The script created `vpa-tls-certs`; the admission controller then became `1/1 Running`. During the load test I also observed brief `postgres` DNS lookup failures in API logs, which corresponded to the HTTP 500 responses; I recorded these rather than treating them as successful requests.

**Figure 12. Troubleshooting evidence.** Insert the VPA `kubectl describe pod` Events showing the missing Secret followed by the final Ready state, and/or the API logs showing the transient `postgres` DNS lookup errors. Do not claim the underlying DNS cause is known unless further evidence supports it.

## 8. Conclusion

The deployment [summarize actual completion] and [summarize actual data persistence, CRUD and routing]. Under the measured load, the API [actual HPA outcome]. The VPA recommended [actual CPU/memory recommendation] for PostgreSQL in Off mode. The main operational lesson from the troubleshooting step was [lesson based on evidence].

## Appendix A. Manifests and source

Include the numbered `k8s/` manifests and the `app/` source/Dockerfile in the repository link. Keep the real `01-secrets.yaml` out of the repository; provide instructions to create it from the example file. The main report should remain within eight pages, excluding this appendix.
