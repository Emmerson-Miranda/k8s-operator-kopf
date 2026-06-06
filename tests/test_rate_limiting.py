"""
Tests for 429 Too Many Requests retry behaviour.

Option 1 (unit tests asserting TemporaryError is raised) lives in
test_create.py / test_update.py / test_delete.py.

Option 2 (full retry cycle) is here: the mock side_effect list simulates
what KOPF does — call the handler, get TemporaryError, wait, call again.
The second call must succeed, proving the handler is idempotent under retry.
"""
import pytest
from unittest.mock import MagicMock

import kopf
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.create import on_create
from my_operator.handlers.update import on_update
from my_operator.handlers.delete import on_delete

SPEC = {'image': 'nginx:latest', 'replicas': 2, 'port': 80}
OLD_SPEC = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}
NEW_SPEC = {'image': 'nginx:2.0', 'replicas': 2, 'port': 80}


def _create(mock_k8s_client, mocker, logger, patch=None):
    mocker.patch('kopf.adopt')
    patch = patch or MagicMock()
    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=patch)
    return patch


def _update(mock_k8s_client, logger):
    patch = MagicMock()
    on_update(spec=NEW_SPEC, old=OLD_SPEC, new=NEW_SPEC,
              name='test-app', namespace='default',
              logger=logger, patch=patch)
    return patch


def _delete(mock_k8s_client, logger):
    on_delete(name='test-app', namespace='default', logger=logger)


# ---------------------------------------------------------------------------
# CREATE — deployment rate-limited then recovers
# ---------------------------------------------------------------------------

def test_create_deployment_429_retries_and_recovers(mock_k8s_client, mocker, logger):
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = [
        ApiException(status=429),  # first attempt: rate limited
        MagicMock(),               # retry: succeeds
    ]

    with pytest.raises(kopf.TemporaryError):
        _create(mock_k8s_client, mocker, logger)

    patch_obj = _create(mock_k8s_client, mocker, logger)

    assert mock_k8s_client['apps'].create_namespaced_deployment.call_count == 2
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


# ---------------------------------------------------------------------------
# CREATE — service rate-limited then recovers
# On retry the deployment already exists (409 → skipped), service succeeds.
# ---------------------------------------------------------------------------

def test_create_service_429_retries_and_recovers(mock_k8s_client, mocker, logger):
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = [
        MagicMock(),               # first attempt: deployment succeeds
        ApiException(status=409),  # retry: deployment already exists, skipped
    ]
    mock_k8s_client['core'].create_namespaced_service.side_effect = [
        ApiException(status=429),  # first attempt: rate limited
        MagicMock(),               # retry: succeeds
    ]

    with pytest.raises(kopf.TemporaryError):
        _create(mock_k8s_client, mocker, logger)

    patch_obj = _create(mock_k8s_client, mocker, logger)

    assert mock_k8s_client['core'].create_namespaced_service.call_count == 2
    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


# ---------------------------------------------------------------------------
# UPDATE — deployment rate-limited then recovers
# ---------------------------------------------------------------------------

def test_update_deployment_429_retries_and_recovers(mock_k8s_client, logger):
    mock_k8s_client['apps'].patch_namespaced_deployment.side_effect = [
        ApiException(status=429),  # first attempt: rate limited
        MagicMock(),               # retry: succeeds
    ]

    with pytest.raises(kopf.TemporaryError):
        _update(mock_k8s_client, logger)

    patch_obj = _update(mock_k8s_client, logger)

    assert mock_k8s_client['apps'].patch_namespaced_deployment.call_count == 2
    patch_obj.status.__setitem__.assert_called_with('message', 'Updated')


# ---------------------------------------------------------------------------
# DELETE — deployment rate-limited then recovers
# ---------------------------------------------------------------------------

def test_delete_deployment_429_retries_and_recovers(mock_k8s_client, logger):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = [
        ApiException(status=429),  # first attempt: rate limited
        MagicMock(),               # retry: succeeds
    ]

    with pytest.raises(kopf.TemporaryError):
        _delete(mock_k8s_client, logger)

    _delete(mock_k8s_client, logger)

    assert mock_k8s_client['apps'].delete_namespaced_deployment.call_count == 2
    mock_k8s_client['core'].delete_namespaced_service.call_count == 1


# ---------------------------------------------------------------------------
# DELETE — service rate-limited then recovers
# On retry the deployment is already gone (404 → skipped), service succeeds.
# ---------------------------------------------------------------------------

def test_delete_service_429_retries_and_recovers(mock_k8s_client, logger):
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = [
        MagicMock(),               # first attempt: deployment deleted
        ApiException(status=404),  # retry: already gone, skipped
    ]
    mock_k8s_client['core'].delete_namespaced_service.side_effect = [
        ApiException(status=429),  # first attempt: rate limited
        MagicMock(),               # retry: succeeds
    ]

    with pytest.raises(kopf.TemporaryError):
        _delete(mock_k8s_client, logger)

    _delete(mock_k8s_client, logger)

    assert mock_k8s_client['core'].delete_namespaced_service.call_count == 2
