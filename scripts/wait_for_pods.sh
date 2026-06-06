#!/usr/bin/env bash
set -euo pipefail
# This script is intended to be used in CI, where we want to wait for the operator and app pods to be running before running the tests.
labels=(app=my-operator app=my-app)
for label in "${labels[@]}"; do
  echo "Waiting for pod with $label ..."
  for i in $(seq 1 10); do
    if kubectl get pods -l "$label" --field-selector=status.phase=Running --no-headers 2>/dev/null | grep -q .; then
      echo "  pod $label is running"
      break
    fi
    if [ "$i" -eq 10 ]; then
      echo "  WARNING: pod with $label not running after 10s, continuing anyway"
    fi
    sleep 1
  done
done
