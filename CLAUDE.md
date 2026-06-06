# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Kubernetes operator built with [KOPF](https://kopf.readthedocs.io/) that manages a `WebApp` custom resource (group `demo.example.com/v1`). The operator provisions a `Deployment` and `ClusterIP Service` for each `WebApp`, handles spec updates, and cleans up child resources on deletion via a finalizer.

Local cluster testing uses [KinD](https://kind.sigs.k8s.io/).

## Setup

```bash
pip install -e ".[dev]"
```

## Commands

```bash
# Run unit tests (no cluster required)
./scripts/run_tests.sh
# Equivalent: pytest tests/ -v --cov=my_operator --cov-report=term-missing

# Run a single test file
pytest tests/test_create.py -v

# Run operator locally (out-of-cluster, requires KUBECONFIG)
kopf run my_operator/operator.py --all-namespaces

# Full KinD cluster test cycle (creates cluster, builds image, runs integration tests, tears down)
./scripts/run_tests_kind.sh

# Watch WebApp resources
kubectl get webapps -w
```

## Architecture

### Package layout

```
my_operator/              # Python package (named my_operator to avoid stdlib conflict)
  operator.py             # KOPF entry-point; imports and registers all handlers
  handlers/
    create.py             # @kopf.on.create — creates Deployment + Service, patches status
    update.py             # @kopf.on.update — diffs spec, patches Deployment, updates status
    delete.py             # @kopf.on.delete — cleans up Deployment + Service (finalizer)
manifests/
  crd.yaml                # WebApp CRD (group: demo.example.com, version: v1) with status sub-resource
  rbac.yaml               # ServiceAccount, ClusterRole, ClusterRoleBinding for the operator
tests/
  conftest.py             # Shared fixtures: fake_webapp dict, mock_k8s_client
  test_create.py          # Unit tests for create handler (mocked k8s client)
  test_update.py          # Unit tests for update handler (mocked k8s client)
scripts/
  run_tests.sh            # Local unit test runner
  run_tests_kind.sh       # Full KinD integration test cycle
Dockerfile                # python:3.12-slim; installs via pyproject.toml; CMD: kopf run
kind-config.yaml          # Single control-plane KinD cluster config
pyproject.toml            # Dependencies: kopf, kubernetes, pytest, pytest-asyncio, pytest-mock
```

### Key design points

- **KOPF handlers** receive `spec`, `name`, `namespace`, `logger`, `patch`, `old`, `new`, `**kwargs` — always accept `**kwargs` to future-proof against new KOPF injections.
- **Child resource ownership** is set via `kopf.adopt()` so KOPF can track and garbage-collect them.
- **Status patching** is done through the `patch` argument (not `kubernetes` client directly) to use the CRD's status sub-resource.
- **Finalizer** is registered on the `WebApp` resource to ensure cleanup of the child `Deployment` and `Service` before the CR is deleted.
- **Unit tests** mock the `kubernetes` client and call handler functions directly — no cluster needed. Integration tests use `kopf.testing.KopfRunner` against a live KinD API server.
- The `WebApp` CRD has `additionalPrinterColumns` so `kubectl get webapps` shows `IMAGE`, `REPLICAS`, and `STATUS`.
