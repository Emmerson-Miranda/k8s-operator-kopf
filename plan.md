# Kubernetes Operator with Python & KOPF — Project Plan

## Overview

A five-phase plan to build, test, and deploy a Kubernetes operator using the [KOPF](https://kopf.readthedocs.io/) framework and a [KinD](https://kind.sigs.k8s.io/) local cluster.

---

## Project Structure

```
my-operator/
├── operator/
│   ├── __init__.py
│   ├── operator.py          # KOPF entry-point
│   └── handlers/
│       ├── __init__.py
│       ├── create.py
│       └── update.py
├── manifests/
│   ├── crd.yaml
│   └── rbac.yaml
├── tests/
│   ├── conftest.py
│   ├── test_create.py
│   └── test_update.py
├── scripts/
│   ├── run_tests.sh
│   └── run_tests_kind.sh
├── Dockerfile
├── kind-config.yaml
└── pyproject.toml
```

---

## Phase 1 — Project Setup

Set up a standard Python package with all required dependencies.

**Key dependencies (`pyproject.toml`):**
- `kopf` — operator framework
- `kubernetes` — official Python client
- `pytest` — test runner
- `pytest-asyncio` — async test support
- `pytest-mock` — mocking utilities

**Tooling:**
- A `Makefile` ties together common commands (`make test`, `make kind-up`, `make deploy`, etc.)
- Virtual environment managed via `venv` or `poetry`

---

## Phase 2 — CRD Definition

Define a simple but realistic custom resource: **`WebApp`** in group `demo.example.com`.

**Spec fields:**

| Field      | Type    | Description              |
|------------|---------|--------------------------|
| `image`    | string  | Container image to run   |
| `replicas` | integer | Number of pod replicas   |
| `port`     | integer | Port to expose           |

**CRD features (`manifests/crd.yaml`):**
- Group: `demo.example.com` / Version: `v1` / Kind: `WebApp`
- `status` sub-resource — allows KOPF to patch status independently of spec
- `additionalPrinterColumns` — so `kubectl get webapps` shows `IMAGE`, `REPLICAS`, and `STATUS`

**Example manifest:**

```yaml
apiVersion: demo.example.com/v1
kind: WebApp
metadata:
  name: my-app
spec:
  image: nginx:latest
  replicas: 2
  port: 80
```

---

## Phase 3 — Operator Logic

Two event handlers wired with KOPF decorators, plus a finalizer for cleanup.

### Create handler (`handlers/create.py`)

```python
@kopf.on.create('demo.example.com', 'v1', 'webapps')
def on_create(spec, name, namespace, logger, patch, **kwargs):
    # 1. Build and create a Deployment
    # 2. Build and create a ClusterIP Service
    # 3. Adopt child resources (set owner references)
    # 4. Patch status: message = "Provisioned"
```

### Update handler (`handlers/update.py`)

```python
@kopf.on.update('demo.example.com', 'v1', 'webapps', field='spec')
def on_update(spec, old, new, name, namespace, logger, patch, **kwargs):
    # 1. Diff old vs new spec fields
    # 2. Patch only the changed fields in the Deployment
    # 3. Patch status: message = "Updated"
```

### Finalizer (cleanup on deletion)

Register a KOPF finalizer on the resource to clean up child `Deployment` and `Service` objects when the `WebApp` is deleted.

---

## Phase 4 — Tests

Two test layers: fast unit tests (no cluster) and integration tests (live API server via KinD).

### Unit tests (`tests/test_create.py`, `tests/test_update.py`)

- Use `pytest-mock` to mock the `kubernetes` client
- Call handler functions directly
- Assert that the correct API methods were called with the correct arguments
- Fast feedback loop — no cluster required

**Fixtures (`tests/conftest.py`):**
- `fake_webapp` — a minimal `WebApp` object dict
- `mock_k8s_client` — patched kubernetes client
- Environment variable stubs

### Integration tests

- Use `kopf.testing.KopfRunner` to run the operator in-process
- Apply a real `WebApp` manifest against the KinD API server
- Assert that a `Deployment` and `Service` appear in the cluster

### Local test runner

**`scripts/run_tests.sh`:**

```bash
#!/usr/bin/env bash
set -euo pipefail
pytest tests/ -v --cov=operator --cov-report=term-missing "$@"
```

---

## Phase 5 — KinD Cluster Integration

Full cluster-based testing and debugging workflow.

### KinD config (`kind-config.yaml`)

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY operator/ ./operator/
CMD ["kopf", "run", "operator/operator.py", "--all-namespaces"]
```

### RBAC (`manifests/rbac.yaml`)

- `ServiceAccount` for the operator
- `ClusterRole` with permissions on `webapps`, `deployments`, `services`, `events`
- `ClusterRoleBinding` linking the two

### Cluster test runner (`scripts/run_tests_kind.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Create cluster
kind create cluster --config kind-config.yaml

# 2. Build and load operator image
docker build -t my-operator:dev .
kind load docker-image my-operator:dev

# 3. Apply CRD and RBAC
kubectl apply -f manifests/

# 4. Deploy operator
kubectl apply -f manifests/operator-deployment.yaml
kubectl rollout status deployment/my-operator

# 5. Run integration tests
pytest tests/ -v -m integration

# 6. Teardown
kind delete cluster
```

---

## Summary

| Phase | Goal | Key output |
|-------|------|------------|
| 1 | Project scaffold | `pyproject.toml`, package layout |
| 2 | Custom resource | `crd.yaml`, `WebApp` schema |
| 3 | Operator logic | `create.py`, `update.py`, finalizer |
| 4 | Tests | Unit + integration test suite, `run_tests.sh` |
| 5 | KinD integration | `Dockerfile`, RBAC, `run_tests_kind.sh` |

---

## Useful Commands

```bash
# Run unit tests locally
./scripts/run_tests.sh

# Run operator locally (out-of-cluster, needs KUBECONFIG)
kopf run operator/operator.py --all-namespaces

# Full cluster test cycle
./scripts/run_tests_kind.sh

# Watch WebApp resources
kubectl get webapps -w
```

---

## References

- [KOPF documentation](https://kopf.readthedocs.io/)
- [KinD documentation](https://kind.sigs.k8s.io/)
- [Kubernetes Python client](https://github.com/kubernetes-client/python)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
