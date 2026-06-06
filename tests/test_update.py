from unittest.mock import MagicMock

from my_operator.handlers.update import on_update


def _call_update(mock_k8s_client, old_spec, new_spec):
    patch_obj = MagicMock()
    on_update(
        spec=new_spec,
        old=old_spec,
        new=new_spec,
        name='test-app',
        namespace='default',
        logger=MagicMock(),
        patch=patch_obj,
    )
    return patch_obj


def test_update_patches_deployment_on_image_change(mock_k8s_client):
    old = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}
    new = {'image': 'nginx:2.0', 'replicas': 2, 'port': 80}

    _call_update(mock_k8s_client, old, new)

    mock_k8s_client['apps'].patch_namespaced_deployment.assert_called_once()


def test_update_patches_deployment_on_replica_change(mock_k8s_client):
    old = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}
    new = {'image': 'nginx:1.0', 'replicas': 5, 'port': 80}

    _call_update(mock_k8s_client, old, new)

    call_args = mock_k8s_client['apps'].patch_namespaced_deployment.call_args
    assert call_args.kwargs['body']['spec']['replicas'] == 5


def test_update_no_patch_when_spec_unchanged(mock_k8s_client):
    spec = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}

    _call_update(mock_k8s_client, spec, spec)

    mock_k8s_client['apps'].patch_namespaced_deployment.assert_not_called()


def test_update_sets_status_updated(mock_k8s_client):
    old = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}
    new = {'image': 'nginx:2.0', 'replicas': 2, 'port': 80}

    patch_obj = _call_update(mock_k8s_client, old, new)

    patch_obj.status.__setitem__.assert_called_with('message', 'Updated')
