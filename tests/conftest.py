import pytest


@pytest.fixture
def fake_webapp():
    return {
        'metadata': {'name': 'test-app', 'namespace': 'default'},
        'spec': {
            'image': 'nginx:latest',
            'replicas': 2,
            'port': 80,
        },
    }


@pytest.fixture
def mock_k8s_client(mocker):
    mock_apps = mocker.patch('kubernetes.client.AppsV1Api')
    mock_core = mocker.patch('kubernetes.client.CoreV1Api')
    return {
        'apps': mock_apps.return_value,
        'core': mock_core.return_value,
    }
