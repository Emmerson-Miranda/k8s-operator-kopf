# k8s-operator-kopf

A Kubernetes operator built with [KOPF](https://kopf.readthedocs.io/) that manages a `WebApp` custom resource. When you apply a `WebApp`, the operator automatically provisions a `Deployment` and a `ClusterIP Service` for it, keeps them in sync as you update the spec, and cleans them up when the resource is deleted.

## How it works

```
kubectl apply -f webapp.yaml
        │
        ▼
  WebApp CR created
        │
        ▼
  KOPF operator (running as a Deployment)
        │
        ├─ on.create → creates Deployment + ClusterIP Service, sets status=Provisioned
        ├─ on.update → patches Deployment (image / replicas), sets status=Updated
        └─ on.delete → deletes Deployment + Service (finalizer ensures cleanup)
```

The `WebApp` spec has three fields:

| Field      | Description                          |
|------------|--------------------------------------|
| `image`    | Container image for the web app      |
| `replicas` | Number of pod replicas               |
| `port`     | Container port exposed by the app    |

## Quick start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run unit tests (no cluster required)
make test

# Spin up a local KinD cluster, deploy the operator, and run the full test cycle
make kind-up

# Tear down the cluster
make kind-down
```

## Example resource

```yaml
apiVersion: demo.example.com/v1
kind: WebApp
metadata:
  name: my-app
spec:
  image: nginx:latest
  replicas: 1
  port: 80
```

Apply it:

```bash
kubectl apply -f manifests-examples/example.yaml

# Trigger an update (changes image to nginx:1.25 and replicas to 2)
kubectl apply -f manifests-examples/example-update.yaml

# Watch the operator react
kubectl get webapps -w
kubectl get pods -l app=my-app
```

## Project layout

```
my_operator/
  operator.py          # KOPF entry-point; registers all handlers
  handlers/
    create.py          # on.create — provisions Deployment + Service
    update.py          # on.update — diffs spec, patches Deployment
    delete.py          # on.delete — cleans up child resources
manifests/
  crd.yaml             # WebApp CRD (group: demo.example.com/v1)
  rbac.yaml            # ServiceAccount, ClusterRole, ClusterRoleBinding
  operator-deployment.yaml
manifests-examples/
  example.yaml         # Sample WebApp (nginx:latest, 1 replica)
  example-update.yaml  # Updated WebApp (nginx:1.25, 2 replicas) — triggers on.update
tests/
  test_create.py       # Unit tests for create handler
  test_update.py       # Unit tests for update handler
scripts/
  run_tests.sh         # Local unit test runner
  run_tests_kind.sh    # Full KinD integration cycle
  wait_for_pods.sh     # Waits for operator and app pods to be Running
Dockerfile             # python:3.12-slim; installs package; runs kopf
kind-config.yaml       # Single control-plane KinD cluster config
```

## Requirements

- Python 3.11+
- Docker
- [KinD](https://kind.sigs.k8s.io/) (`brew install kind`)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
