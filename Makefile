.PHONY: test kind-up kind-down deploy clean

test:
	./scripts/run_tests.sh

docker-build:
	docker build -t my-operator:dev .

kind-up: docker-build
	kind create cluster --config kind-config.yaml 2>/dev/null || true
	kind load docker-image my-operator:dev

	kubectl apply -f manifests/
	kubectl rollout status deployment/my-operator

	kubectl apply -f manifests-examples/example.yaml

	./scripts/wait_for_pods.sh 

	kubectl apply -f manifests-examples/example-update.yaml

	pytest tests/ -v
	TEST_EXIT=$?

	echo "--- Operator logs ---"
	kubectl logs deployment/my-operator --all-containers || true

	kubectl get pods

	curl http://localhost:8000/metrics | grep handler | head -n 5

	kubectl config current-context

	echo "Cluster started with kind, you can run 'make kind-down' to delete it."

kind-down:
	kind delete cluster

deploy:
	kubectl apply -f manifests/

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
