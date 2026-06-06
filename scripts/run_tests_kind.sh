#!/usr/bin/env bash
set -euo pipefail

kind delete cluster 2>/dev/null || true
kind create cluster --config kind-config.yaml

docker build -t my-operator:dev .
kind load docker-image my-operator:dev

kubectl apply -f manifests/
kubectl rollout status deployment/my-operator

kubectl apply -f manifests-examples/example.yaml

./scripts/wait_for_pods.sh

kubectl apply -f manifests-examples/example-update.yaml

pytest tests/ -v
TEST_EXIT=$?

kubectl delete -f manifests-examples/example.yaml

echo "--- Operator logs ---"
kubectl logs deployment/my-operator --all-containers || true

kind delete cluster
exit $TEST_EXIT
