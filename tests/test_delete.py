import pytest
from unittest.mock import MagicMock

import kopf
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.delete import on_delete


def _call_delete(mock_k8s_client, logger):
    on_delete(name='test-app', namespace='default', logger=logger)


def test_delete_removes_deployment_and_service(mock_k8s_client, logger):
    _call_delete(mock_k8s_client, logger)
    mock_k8s_client['apps'].delete_namespaced_deployment.assert_called_once()
    mock_k8s_client['core'].delete_namespaced_service.assert_called_once()


def test_delete_deployment_not_found_continues(mock_k8s_client, logger):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=404)
    _call_delete(mock_k8s_client, logger)
    mock_k8s_client['core'].delete_namespaced_service.assert_called_once()


def test_delete_deployment_server_error_raises_temporary_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] TemporaryError name=test-app ns=default' in caplog.text
    mock_k8s_client['core'].delete_namespaced_service.assert_not_called()


def test_delete_deployment_client_error_raises_permanent_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=403)

    with pytest.raises(kopf.PermanentError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] PermanentError name=test-app ns=default' in caplog.text
    mock_k8s_client['core'].delete_namespaced_service.assert_not_called()


def test_delete_service_not_found_continues(mock_k8s_client, logger):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=404)
    _call_delete(mock_k8s_client, logger)
    mock_k8s_client['apps'].delete_namespaced_deployment.assert_called_once()


def test_delete_service_server_error_raises_temporary_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=503)

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] TemporaryError name=test-app ns=default' in caplog.text


def test_delete_service_client_error_raises_permanent_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=422)

    with pytest.raises(kopf.PermanentError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] PermanentError name=test-app ns=default' in caplog.text


def test_delete_deployment_rate_limited_raises_temporary_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=429)

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] TemporaryError name=test-app ns=default' in caplog.text


def test_delete_service_rate_limited_raises_temporary_error(
        mock_k8s_client, logger, caplog):
    mock_k8s_client['core'].delete_namespaced_service.side_effect = ApiException(status=429)

    with pytest.raises(kopf.TemporaryError):
        _call_delete(mock_k8s_client, logger)

    assert '[DELETE] TemporaryError name=test-app ns=default' in caplog.text
