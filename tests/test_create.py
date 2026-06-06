import pytest
from unittest.mock import MagicMock

import kopf
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.create import on_create


def _call_create(mock_k8s_client, mocker, spec=None, patch=None):
    mocker.patch('kopf.adopt')
    spec = spec or {'image': 'nginx:latest', 'replicas': 2, 'port': 80}
    patch = patch or MagicMock()
    on_create(
        spec=spec,
        name='test-app',
        namespace='default',
        logger=MagicMock(),
        patch=patch,
    )
    return patch


def test_create_provisions_deployment(mock_k8s_client, mocker):
    patch = _call_create(mock_k8s_client, mocker)
    call_kwargs = mock_k8s_client['apps'].create_namespaced_deployment.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_provisions_service(mock_k8s_client, mocker):
    patch = _call_create(mock_k8s_client, mocker)
    call_kwargs = mock_k8s_client['core'].create_namespaced_service.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_sets_status_provisioned(mock_k8s_client, mocker):
    patch_obj = MagicMock()
    _call_create(mock_k8s_client, mocker, patch=patch_obj)
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_adopts_child_resources(mock_k8s_client, mocker):
    adopt = mocker.patch('kopf.adopt')
    on_create(
        spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
        name='test-app',
        namespace='default',
        logger=MagicMock(),
        patch=MagicMock(),
    )
    assert adopt.call_count == 2


def test_create_missing_spec_field_raises_permanent_error(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    logger = MagicMock()
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(
            spec={'image': 'nginx:latest'},  # missing replicas and port
            name='test-app',
            namespace='default',
            logger=logger,
            patch=patch_obj,
        )

    logger.info.assert_any_call('[CREATE] PermanentError name=test-app ns=default')
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_deployment_conflict_skips_and_continues(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=409)

    patch_obj = MagicMock()
    on_create(
        spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
        name='test-app',
        namespace='default',
        logger=MagicMock(),
        patch=patch_obj,
    )

    mock_k8s_client['core'].create_namespaced_service.assert_called_once()
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_deployment_server_error_raises_temporary_error(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=500)
    logger = MagicMock()
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(
            spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
            name='test-app',
            namespace='default',
            logger=logger,
            patch=patch_obj,
        )

    logger.info.assert_any_call('[CREATE] TemporaryError name=test-app ns=default')
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_deployment_client_error_raises_permanent_error(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=403)
    logger = MagicMock()
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(
            spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
            name='test-app',
            namespace='default',
            logger=logger,
            patch=patch_obj,
        )

    logger.info.assert_any_call('[CREATE] PermanentError name=test-app ns=default')
    assert 'Error' in patch_obj.status.__setitem__.call_args[0][1]


def test_create_service_conflict_skips_and_continues(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=409)

    patch_obj = MagicMock()
    on_create(
        spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
        name='test-app',
        namespace='default',
        logger=MagicMock(),
        patch=patch_obj,
    )

    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_service_server_error_raises_temporary_error(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=503)
    logger = MagicMock()
    patch_obj = MagicMock()

    with pytest.raises(kopf.TemporaryError):
        on_create(
            spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
            name='test-app',
            namespace='default',
            logger=logger,
            patch=patch_obj,
        )

    logger.info.assert_any_call('[CREATE] TemporaryError name=test-app ns=default')


def test_create_service_client_error_raises_permanent_error(mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    mock_k8s_client['core'].create_namespaced_service.side_effect = ApiException(status=422)
    logger = MagicMock()
    patch_obj = MagicMock()

    with pytest.raises(kopf.PermanentError):
        on_create(
            spec={'image': 'nginx:latest', 'replicas': 2, 'port': 80},
            name='test-app',
            namespace='default',
            logger=logger,
            patch=patch_obj,
        )

    logger.info.assert_any_call('[CREATE] PermanentError name=test-app ns=default')
