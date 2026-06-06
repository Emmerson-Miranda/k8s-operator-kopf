# Kubernetes Operator with Python & KOPF — Project Plan

## Overview

A phased plan to build, harden, and observe a Kubernetes operator using the [KOPF](https://kopf.readthedocs.io/) framework and a [KinD](https://kind.sigs.k8s.io/) local cluster.

---

## Project Structure

```
my-operator/
├── my_operator/
│   ├── __init__.py
│   ├── operator.py             # KOPF entry-point; registers handlers + starts metrics
│   ├── config.py               # All env-var configuration (single source of truth)
│   ├── metrics.py              # Prometheus metrics + sliding-window error collectors
│   └── handlers/
│       ├── __init__.py
│       ├── create.py           # @kopf.on.create
│       ├── update.py           # @kopf.on.update
│       └── delete.py           # @kopf.on.delete (finalizer)
├── manifests/
│   ├── crd.yaml
│   ├── rbac.yaml
│   ├── operator-deployment.yaml
│   └── metrics-service.yaml
├── manifests-examples/
│   ├── example.yaml
│   └── example-update.yaml
├── tests/
│   ├── conftest.py
│   ├── test_create.py
│   ├── test_update.py
│   ├── test_delete.py
│   ├── test_rate_limiting.py
│   └── test_metrics.py
├── scripts/
│   ├── run_tests.sh
│   ├── run_tests_kind.sh
│   └── wait_for_pods.sh
├── Dockerfile
├── kind-config.yaml
└── pyproject.toml
```

---

## Phase 1 — Project Setup ✅

Standard Python package with all required dependencies.

**`pyproject.toml` dependencies:**
- `kopf` — operator framework
- `kubernetes` — official Python client
- `prometheus-client` — metrics export
- `pytest`, `pytest-asyncio`, `pytest-mock` — test tooling

**pytest config:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
log_cli = true
log_cli_level = "INFO"
log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
```

---

## Phase 2 — CRD Definition ✅

Custom resource **`WebApp`** in group `demo.example.com`.

**Spec fields:**

| Field      | Type    | Description            |
|------------|---------|------------------------|
| `image`    | string  | Container image to run |
| `replicas` | integer | Number of pod replicas |
| `port`     | integer | Port to expose         |

**CRD features (`manifests/crd.yaml`):**
- Group: `demo.example.com` / Version: `v1` / Kind: `WebApp`
- `status` sub-resource
- `additionalPrinterColumns` — `IMAGE`, `REPLICAS`, `STATUS`

---

## Phase 3 — Operator Logic ✅

Three event handlers and a finalizer.

### Create handler (`handlers/create.py`)

```python
@kopf.on.create(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
                retries=MAX_RETRIES, backoff=RETRY_BACKOFF)
def on_create(spec, name, namespace, logger, patch, **kwargs):
    # 1. Validate required spec fields → PermanentError on missing
    # 2. Create Deployment via apps/v1 API
    # 3. Create ClusterIP Service via core/v1 API
    # 4. kopf.adopt() child resources
    # 5. ACTIVE_WEBAPPS.inc(); patch.status['message'] = 'Provisioned'
```

### Update handler (`handlers/update.py`)

```python
@kopf.on.update(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
                retries=MAX_RETRIES, backoff=RETRY_BACKOFF)
def on_update(spec, old, new, name, namespace, logger, patch, **kwargs):
    # 1. Diff spec fields; skip if unchanged
    # 2. Patch Deployment; patch.status['message'] = 'Updated'
```

### Delete handler / finalizer (`handlers/delete.py`)

```python
@kopf.on.delete(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL)
def on_delete(name, namespace, logger, **kwargs):
    # 1. Delete Deployment
    # 2. Delete Service
    # 3. ACTIVE_WEBAPPS.dec()
```

---

## Phase 4 — Tests ✅

| File | Coverage |
|------|----------|
| `test_create.py` | Create handler — success, idempotency (409), 4xx/5xx/429 errors |
| `test_update.py` | Update handler — field diffs, no-op, 4xx/5xx/429 errors |
| `test_delete.py` | Delete handler — success, 404 skip, 4xx/5xx errors |
| `test_rate_limiting.py` | Retry cycle — mock `side_effect` list simulating 429 → eventual success |
| `test_metrics.py` | Prometheus counters, histogram, active gauge, sliding-window collectors |

**`tests/conftest.py` fixtures:**
- `fake_webapp` — minimal WebApp dict
- `mock_k8s_client` — patched `AppsV1Api` + `CoreV1Api`
- `logger` — real `logging.getLogger` (log output visible in pytest)

---

## Phase 5 — KinD Cluster Integration ✅

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install .
CMD ["kopf", "run", "my_operator/operator.py", "--all-namespaces"]
```

### RBAC (`manifests/rbac.yaml`)

ClusterRole grants:
- `webapps` — full CRUD
- `deployments`, `services` — create/get/patch/delete
- `events` — create/patch
- `customresourcedefinitions` — get/list/watch (required by KOPF startup)

### Cluster test runner (`scripts/run_tests_kind.sh`)

```
1. kind delete cluster (cleanup any prior run)
2. kind create cluster --config kind-config.yaml
3. docker build + kind load docker-image
4. kubectl apply -f manifests/
5. kubectl rollout status deployment/my-operator
6. kubectl apply -f manifests-examples/example.yaml
7. ./scripts/wait_for_pods.sh (waits up to 10s for app + operator pods)
8. kubectl apply -f manifests-examples/example-update.yaml
9. pytest tests/ -v
10. kubectl delete -f manifests-examples/example.yaml
11. Print operator logs
12. kind delete cluster
```

---

## Phase 6 — Error Handling & Resilience ✅

Branch: `monitoring` (formerly `error-handling` / `testing-error-handling`)

### `my_operator/config.py`

Single source of truth for all runtime configuration via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `OPERATOR_GROUP` | `demo.example.com` | CRD group |
| `OPERATOR_VERSION` | `v1` | CRD version |
| `OPERATOR_PLURAL` | `webapps` | CRD plural |
| `SERVICE_TYPE` | `ClusterIP` | Kubernetes Service type |
| `RETRY_DELAY` | `10` | TemporaryError delay (seconds) |
| `MAX_RETRIES` | `10` | Handler max retries |
| `RETRY_BACKOFF` | `60` | KOPF backoff (seconds) |
| `METRICS_PORT` | `8000` | Prometheus HTTP port |
| `ERROR_WINDOW_SECONDS` | `60` | Sliding window size |

### Error classification

| HTTP status | Error type | Behaviour |
|---|---|---|
| 404 (Not Found) | skip / log | idempotent, no raise |
| 409 (Conflict) | skip / log | resource already exists |
| 429 (Too Many Requests) | `TemporaryError` | retried with backoff |
| 5xx (Server Error) | `TemporaryError` | retried with backoff |
| 4xx (Client Error) | `PermanentError` | not retried |
| missing spec field | `PermanentError` | not retried |

All raises are preceded by `logger.info('[HANDLER] ErrorType name=... ns=...')`.

---

## Phase 7 — Prometheus Metrics ✅

Branch: `monitoring`

### `my_operator/metrics.py`

| Metric | Type | Labels | Description |
|---|---|---|---|
| `webapp_events_total` | Counter | `handler`, `status` | Total handler invocations |
| `webapp_handler_duration_seconds` | Histogram | `handler` | Handler execution time |
| `webapp_active_total` | Gauge | — | Active WebApp resources |
| `webapp_permanent_errors_last_minute` | Gauge (sliding) | `handler` | PermanentErrors in last N seconds |
| `webapp_temporary_errors_last_minute` | Gauge (sliding) | `handler` | TemporaryErrors in last N seconds |

Sliding-window collectors use a `collections.deque` + `threading.Lock`. Events older than `ERROR_WINDOW_SECONDS` are purged on each scrape.

### `track_handler` context manager

Wraps every handler body: records duration, increments `EVENTS_TOTAL`, and on error routes to the correct sliding-window collector before re-raising.

### Kubernetes manifests

- `manifests/operator-deployment.yaml` — all env vars declared; `containerPort: 8000`
- `manifests/metrics-service.yaml` — `NodePort` Service (`nodePort: 30800`) with `prometheus.io/scrape: "true"` annotations
- `kind-config.yaml` — `extraPortMappings` forwards host port `8000` → node port `30800`, enabling `curl http://localhost:8000/metrics` from the host machine

---

## Summary

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Project scaffold | ✅ Done |
| 2 | Custom resource | ✅ Done |
| 3 | Operator logic | ✅ Done |
| 4 | Tests | ✅ Done — 55 tests, 93% coverage |
| 5 | KinD integration | ✅ Done |
| 6 | Error handling & resilience | ✅ Done |
| 7 | Prometheus metrics | ✅ Done |

---

## Useful Commands

```bash
# Run unit tests locally
./scripts/run_tests.sh

# Run a single test file
pytest tests/test_metrics.py -v

# Run operator locally (out-of-cluster, needs KUBECONFIG)
kopf run my_operator/operator.py --all-namespaces

# Full KinD cluster test cycle
./scripts/run_tests_kind.sh

# Watch WebApp resources
kubectl get webapps -w

# Check metrics endpoint — local (out-of-cluster)
curl http://localhost:8000/metrics

# Check metrics endpoint — in-cluster via KinD extraPortMappings (host port 8000 → nodePort 30800)
curl http://localhost:8000/metrics
```

---

## References

- [KOPF documentation](https://kopf.readthedocs.io/)
- [KinD documentation](https://kind.sigs.k8s.io/)
- [Kubernetes Python client](https://github.com/kubernetes-client/python)
- [prometheus-client](https://github.com/prometheus/client_python)
