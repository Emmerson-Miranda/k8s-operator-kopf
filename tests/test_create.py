from unittest.mock import MagicMock

from my_operator.handlers.create import on_create


def test_create_provisions_deployment(fake_webapp, mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')

    on_create(
        spec=fake_webapp['spec'],
        name=fake_webapp['metadata']['name'],
        namespace=fake_webapp['metadata']['namespace'],
        logger=MagicMock(),
        patch=MagicMock(),
    )

    call_kwargs = mock_k8s_client['apps'].create_namespaced_deployment.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_provisions_service(fake_webapp, mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')

    on_create(
        spec=fake_webapp['spec'],
        name=fake_webapp['metadata']['name'],
        namespace=fake_webapp['metadata']['namespace'],
        logger=MagicMock(),
        patch=MagicMock(),
    )

    call_kwargs = mock_k8s_client['core'].create_namespaced_service.call_args
    assert call_kwargs.kwargs['namespace'] == 'default'


def test_create_sets_status_provisioned(fake_webapp, mock_k8s_client, mocker):
    mocker.patch('kopf.adopt')
    patch_obj = MagicMock()

    on_create(
        spec=fake_webapp['spec'],
        name=fake_webapp['metadata']['name'],
        namespace=fake_webapp['metadata']['namespace'],
        logger=MagicMock(),
        patch=patch_obj,
    )

    patch_obj.status.__setitem__.assert_called_with('message', 'Provisioned')


def test_create_adopts_child_resources(fake_webapp, mock_k8s_client, mocker):
    adopt = mocker.patch('kopf.adopt')

    on_create(
        spec=fake_webapp['spec'],
        name=fake_webapp['metadata']['name'],
        namespace=fake_webapp['metadata']['namespace'],
        logger=MagicMock(),
        patch=MagicMock(),
    )

    assert adopt.call_count == 2
