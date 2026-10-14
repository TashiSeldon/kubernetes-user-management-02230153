# Kubernetes User Management Update and Diagnostic Report

Student ID: 02230153
Namespace: `usermgmt-02230153`

## Existing project

The project is a Flask REST API running in a two-replica Kubernetes Deployment, with PostgreSQL in a one-replica StatefulSet using a headless Service and a 1 GiB `volumeClaimTemplates` claim. An Ingress routes the student-specific host to the API Service. The API is configured with liveness, readiness, and startup probes, CPU and memory requests and limits, an HPA targeting 50% CPU with 2–6 replicas, and a PostgreSQL VPA in `Off` mode.

## Assignment checklist

| Milestone | Existing implementation | Status |
|---|---|---|
| M1: cluster and platform | Minikube, Ingress, metrics-server, VPA components, manifest-created namespace, default StorageClass | Evidence was previously supplied; platform state must be running at demonstration time. |
| M2: database and persistence | Secret template, headless `postgres` Service, one-replica StatefulSet, 1 GiB claim template, requests and limits | Implemented. User supplied a successful Pod recreation persistence result. Preserve the PVC. |
| M3: API | Versioned image tag, ConfigMap and Secret references, two initial replicas, ClusterIP Service, CRUD routes, health/readiness/startup probes and resources | Implemented; this update improves request concurrency and connection cleanup. Rebuild and redeploy to apply it. |
| M4: Ingress | `nginx` Ingress host `usermgmt-02230153.local` routing to `api:80` | Implemented. Host mapping and routing results were previously supplied. |
| M5: autoscaling | HPA `autoscaling/v2`, 50% CPU, 2–6 replicas; PostgreSQL VPA with `Off`; metrics and timeline script | Implemented. HPA scale-up/down evidence was previously supplied. Newer load results show different behavior at lower concurrency. |
| M6: report and demonstration | Report, architecture diagram, screenshots, troubleshooting discussion, repository | Report and evidence were prepared separately. Repository access for the assessor still needs confirmation. |

The assignment requires a report of no more than eight pages excluding a separate manifest appendix, and a live demonstration of up to ten minutes. The project archive here contains deployment code and documentation, not the report document.

## Diagnostic findings

### HTTP 503 and client timeouts

The earlier 3-minute test at 50 clients returned 11,168 responses: 8,284 HTTP 200 and 2,884 HTTP 503 (25.8%), at about 61.81 requests/second. The Ingress log showed `connect() failed (111: Connection refused)` to `10.244.0.11:5000`. This confirms a failed TCP connection to an API endpoint at that time, but does not establish why the endpoint was refusing connections.

The later 30-second test at 10 clients returned 1,167 HTTP 200 responses, no reported failures, an average response time of 0.2589 seconds, and 38.37 requests/second. The 60-second test at 25 clients returned 984 HTTP 200 responses and 9 client timeouts; it averaged 1.535 seconds, had a 4.0166-second 95th percentile, and a 19.6914-second slowest response. `hey` continued for about 73.3 seconds while requests completed. This is evidence of load-sensitive latency/timeouts, not evidence that the earlier 503 condition was fixed. These tests used different concurrency levels and are not a direct like-for-like comparison.

After the code/configuration update, one 30-second test at 10 clients returned 615 HTTP 200 responses and no reported errors. A later 60-second test at 10 clients returned 1,600 HTTP 200 responses with no reported HTTP failures, 26.56 requests/second, a 0.376-second average, 0.571-second 95th percentile, and 0.901-second slowest response. These are user-supplied runs at moderate concurrency and do not establish behavior under the assignment's 50-client load.

A later three-minute run at 50 clients targeted `http://usermgmt-02230153.local:8080/users`. `hey` reported 5,596 HTTP 200 and 15 HTTP 503 responses among 5,611 responses (about 0.27%), at 30.9955 requests/second, 1.6088-second mean latency, and 7.12-second maximum latency. The listener bound to port 8080 during that load run was not shown in the supplied output, so the test path should not be labeled as Ingress without that confirmation. The cause of the lower observed 503 proportion versus the earlier 25.8% run is unconfirmed; do not attribute it to a port-forward or code change.

In a separate routing check through the Ingress controller port-forward on host port 8081, `curl.exe -i http://usermgmt-02230153.local:8081/users` returned HTTP 200 and the persisted user record. A request to `http://127.0.0.1:8081/users` with `Host: other.local` returned NGINX HTTP 404. This confirms the configured Ingress host routes to the API and an unmatched host does not return the application user list. These checks were separate from the 8080 load run.

The latest three-minute, 50-client run used the explicitly confirmed Ingress forward `127.0.0.1:8086 -> 80` and targeted `http://usermgmt-02230153.local:8086/users`. It returned 3,835 HTTP 200 and 23 HTTP 503 responses (3,858 total; about 0.60% HTTP 503), with 21.26 requests/second, 2.3414-second average latency, 5.2014-second 95th-percentile latency, and 10.2046-second maximum latency. A separate curl request to the configured hostname on port 8086 returned HTTP 200 and the persistent record. The forward terminal also logged several local connections forcibly closed by the remote host at about 09:40:11, immediately after the 181-second run ended; the supplied evidence does not link these messages to individual HTTP 503 responses or establish their cause. This run confirms that HTTP 503 responses still occur under the 50-client load. No HPA timeline was supplied with this run.

The accompanying HPA monitor evidence recorded CPU rising from 4% to 197%, desired replicas increasing to six, and all six API Pods Ready by 09:09. At 09:12:47, CPU was 5% while six replicas remained. That run demonstrates scale-up and readiness, but the captured interval does not show scale-down to two. An earlier, separate cooldown record returned to two; it must not be presented as the cooldown phase of the later load run.

At a later snapshot, both API Pods were Ready and the Service endpoints were `10.244.0.5` and `10.244.0.7`; their restarts were about 106 minutes earlier. The previous upstream address `.11` was no longer listed. Ingress logs queried for the last five minutes returned no matching connection errors, and the API logs returned no output. These were not captured concurrently with a reproduced 503, so they cannot identify the cause. The likely areas to watch during a repeat are synchronous worker saturation, probe delays, Pod restarts, and EndpointSlice changes. The exact root cause remains unconfirmed.

### Database DNS and readiness

An earlier API log recorded a temporary failure resolving the Service name `postgres`; later DNS checks resolved `postgres` and its namespace-qualified name to the PostgreSQL Service IP. This confirms a historical transient DNS resolution error and later successful resolution, but the cause of the earlier interruption is unknown. No Pod IP is hardcoded in the code or manifests.

A PostgreSQL readiness probe once timed out at its one-second default, while a later `pg_isready` reported that PostgreSQL accepted connections. This is consistent with a transient delay; it does not establish current database failure. The readiness probe now has a two-second timeout.

The API readiness endpoint checks the database with `SELECT 1`; `/healthz` only checks the process. Earlier reports of probe timeouts and Pod restarts are historical evidence. The most recent supplied API snapshot showed both Pods Ready with no recent restarts, but no concurrent probe trace was provided for the failing load test.

### Update deployment supplied by the student

The student successfully applied the updated PostgreSQL and API manifests, built and loaded `usermgmt-api:1.0`, and received a successful API Deployment rollout. The new API Pods were `1/1 Running` with zero restarts. The PostgreSQL Pod became Ready after its StatefulSet update; its 1 GiB PVC remained `Bound` to the same volume, so the update did not delete the claim. A later HPA snapshot showed `cpu: 4%/50%` with two replicas at low load; a subsequent 50-client run reached six replicas. The VPA was observed in `Off` mode and provided database recommendations.

The updated monitor recorded CPU values of 2% and 3%, then `N/A` on two samples, with desired/current replicas remaining 2. It no longer crashes when the HPA omits current metrics. A temporary Ready API Pod count of 3 occurred during the rolling update while an old Pod was terminating; the next samples showed 2. A subsequent check showed both Pods Ready, `kubectl top pods` returning CPU and memory for the API and PostgreSQL, Metrics Server APIService available, and the HPA reporting 4% CPU against its 50% target. Recent HPA events explain the earlier `N/A` samples: the resource metrics API temporarily returned no CPU metrics and later reported that targeted Pods might be unready. This is consistent with a transient post-rollout metrics gap; it is not evidence of a continuing Metrics Server outage.

## Changes made

| File | Original problem or limitation | Change made | Reason |
|---|---|---|---|
| `app/app.py` | Psycopg2 connection context managers handled transactions, but the application did not explicitly close each connection. API database connection failures were not mapped to an intentional service-unavailable response. | Added a connection context manager that commits/rolls back and always closes the connection; added two bounded connection attempts for normal requests; limited startup initialization to bounded retries; kept readiness to a single quick attempt; added a logged HTTP 503 handler for database `OperationalError`. | Explicit cleanup and bounded retries improve connection hygiene and tolerate a brief connection interruption. Returning 503 is appropriate when the database cannot serve the request. This does not prove the previous Ingress-level refused connection is fixed. |
| `app/Dockerfile` | Gunicorn used two synchronous workers and did not emit access logs to container output. | Changed to two `gthread` workers with four threads each and enabled stdout access/error logs. | The 25-client test showed long tail latency and client timeouts. Threads provide additional concurrent request slots for this I/O-bound API, while access logs make HTTP status and request behavior observable. This is a mitigation to validate, not a proven root-cause correction. |
| `k8s/03-api.yaml` | Connection retry controls were not configurable; default one-second probes produced timeout warnings; startup initialization can retry while waiting for PostgreSQL. | Added ConfigMap values for two-second connection timeout and two connection attempts; set liveness/readiness probe timeouts to two/three seconds; expanded startup probe allowance to 120 seconds. | These settings are bounded and aligned with the observed slow starts and one-second probe timeouts. CPU/memory requests and limits, HPA target and replica range remain unchanged. |
| `k8s/02-postgres.yaml` | The readiness probe used Kubernetes' one-second default, and one one-second timeout was observed. | Set its timeout to two seconds and failure threshold to three. | Allows a small transient scheduling/database delay while still marking repeated failures unready. |
| `monitor-hpa.ps1` | It failed when current CPU metrics were missing, could continue against the wrong cluster context or missing namespace, and overwrote the same CSV on each run. | Added a Minikube/namespace preflight check, safe `N/A` handling for absent metrics, recoverable sample collection warnings, and a timestamped CSV output path. | Prevents the null-array failure seen in earlier use, avoids recording misleading samples from the wrong context, and preserves earlier timeline evidence. |
| `README.md` | Windows instructions did not consistently use an unprivileged Ingress port-forward, lacked an exact project clone command, and did not collect enough endpoint/log evidence for the reported errors. | Added the exact GitHub clone command; documented the VPA Git Bash path-conversion workaround; standardized Windows Ingress checks on port 8081; added PostgreSQL readiness, EndpointSlice, logs, events, HPA/VPA and cooldown commands; retained the existing Secret and PVC safeguards. | Makes clean deployment and evidence collection reproducible while avoiding privileged-port conflicts and accidental data deletion. |

## Validation performed here

- Python syntax compilation passed for `app/app.py` using Python's in-memory `compile` check.
- PowerShell parser accepted `monitor-hpa.ps1`.
- `git diff --check` passed for the changes reviewed in the prior work.
- YAML parsing and application-runtime tests were not run here; the available bundled Python runtime has no YAML parser or Flask installation.
- Live cluster checks and a new Docker build could not run in this environment: access to the user's kubeconfig and Docker Engine named pipe was denied. The user supplied Windows output confirming image build/load, successful rollout, bound PVC, API CRUD/persistence, metrics availability and the load-test results above. These are user-supplied results, not commands executed in this review environment.

## Remaining verification

1. For complete Milestone 5 evidence, collect HPA samples alongside the 8086 load test and through cooldown, including the later scale-down to two replicas. The latest load result has no accompanying HPA timeline; an earlier separate timeline showed cooldown but was not captured with this experiment.
2. Preserve the existing user record and PVC. The user already supplied a successful Pod-recreation persistence result; do not repeat it unless needed, and never delete the PVC or namespace.
3. Verify the assessor can access the GitHub repository. A previous repository screenshot showed it as private; this review did not change its visibility.
