import pytest
from unittest.mock import MagicMock

import kopf
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.delete import on_delete


def _call_delete(mock_k8s_client, logger=None):
    on_delete(
        name='test-app',
        namespace='default',
        logger=logger or MagicMock(),
    )


def test_delete_removes_deployment_and_service(mock_k8s_client):
    _call_delete(mock_k8s_client)
    mock_k8s_client['apps'].delete_namespaced_deployment.assert_called_once()
    mock_k8s_client['core'].delete_namespaced_service.assert_called_once()


def test_delete_deployment_not_found_continues(mock_k8s_client):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=404)
    _call_delete(mock_k8s_client)
    mock_k8s_client['core'].delete_namespaced_service.assert_called_once()


def test_delete_deployment_server_error_raises_temporary_error(mock_k8s_client):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=500)
    logger = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger=logger)

    logger.info.assert_any_call('[DELETE] TemporaryError name=test-app ns=default')
    mock_k8s_client['core'].delete_namespaced_service.assert_not_called()


def test_delete_deployment_client_error_raises_permanent_error(mock_k8s_client):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=403)
    logger = MagicMock()

    with pytest.raises(kopf.PermanentError):
        _call_delete(mock_k8s_client, logger=logger)

    logger.info.assert_any_call('[DELETE] PermanentError name=test-app ns=default')
    mock_k8s_client['core'].delete_namespaced_service.assert_not_called()


def test_delete_service_not_found_continues(mock_k8s_client):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=404)
    _call_delete(mock_k8s_client)
    mock_k8s_client['apps'].delete_namespaced_deployment.assert_called_once()


def test_delete_service_server_error_raises_temporary_error(mock_k8s_client):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=503)
    logger = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger=logger)

    logger.info.assert_any_call('[DELETE] TemporaryError name=test-app ns=default')


def test_delete_service_client_error_raises_permanent_error(mock_k8s_client):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=422)
    logger = MagicMock()

    with pytest.raises(kopf.PermanentError):
        _call_delete(mock_k8s_client, logger=logger)

    logger.info.assert_any_call('[DELETE] PermanentError name=test-app ns=default')
