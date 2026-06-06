import pytest
from unittest.mock import MagicMock

import kopf
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.create import on_create

SPEC = {'image': 'nginx:latest', 'replicas': 2, 'port': 80}


def _call_create(mock_k8s_client, mocker, logger, spec=None, patch=None):
    mocker.patch('kopf.adopt')
    patch = patch or MagicMock()
    on_create(
        spec=spec or SPEC,
        name='test-app',
        namespace='default',
        logger=logger,
        patch=patch,
    )
    return patch


def test_create_provisions_deployment(mock_k8s_client, mocker, logger):
    _call_create(mock_k8s_client, mocker, logger)
    call_kwargs = mock_k8s_client['apps'].create_namespaced_deployment.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_provisions_service(mock_k8s_client, mocker, logger):
    _call_create(mock_k8s_client, mocker, logger)
    call_kwargs = mock_k8s_client['core'].create_namespaced_service.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_sets_status_provisioned(mock_k8s_client, mocker, logger):
    patch_obj = MagicMock()
    _call_create(mock_k8s_client, mocker, logger, patch=patch_obj)
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_adopts_child_resources(mock_k8s_client, mocker, logger):
    adopt = mocker.patch('kopf.adopt')
    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=MagicMock())
    assert adopt.call_count == 2


def test_create_missing_spec_field_raises_permanent_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(spec={'image': 'nginx:latest'}, name='test-app',
                  namespace='default', logger=logger, patch=patch_obj)

    assert '[CREATE] PermanentError name=test-app ns=default' in caplog.text
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_deployment_conflict_skips_and_continues(
        mock_k8s_client, mocker, logger):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=409)

    patch_obj = MagicMock()
    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=patch_obj)

    mock_k8s_client['core'].create_namespaced_service.assert_called_once()
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_deployment_server_error_raises_temporary_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=500)
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] TemporaryError name=test-app ns=default' in caplog.text
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_deployment_client_error_raises_permanent_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=403)
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] PermanentError name=test-app ns=default' in caplog.text
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_deployment_rate_limited_raises_temporary_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=429)
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] TemporaryError name=test-app ns=default' in caplog.text


def test_create_service_conflict_skips_and_continues(
        mock_k8s_client, mocker, logger):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=409)

    patch_obj = MagicMock()
    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=patch_obj)

    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_service_server_error_raises_temporary_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=503)
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] TemporaryError name=test-app ns=default' in caplog.text


def test_create_service_client_error_raises_permanent_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=422)
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] PermanentError name=test-app ns=default' in caplog.text


def test_create_service_rate_limited_raises_temporary_error(
        mock_k8s_client, mocker, logger, caplog):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=429)
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=patch_obj)

    assert '[CREATE] TemporaryError name=test-app ns=default' in caplog.text
