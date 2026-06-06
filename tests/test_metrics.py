from unittest.mock import MagicMock

import kopf
import pytest
from kubernetes.client.exceptions import ApiException

from my_operator.handlers.create import on_create
from my_operator.handlers.update import on_update
from my_operator.handlers.delete import on_delete

SPEC = {'image': 'nginx:latest', 'replicas': 2, 'port': 80}
OLD_SPEC = {'image': 'nginx:1.0', 'replicas': 2, 'port': 80}
NEW_SPEC = {'image': 'nginx:2.0', 'replicas': 2, 'port': 80}


@pytest.fixture(autouse=True)
def reset_metrics():
    import my_operator.metrics as m
    m.ACTIVE_WEBAPPS._value.set(0)
    m.EVENTS_TOTAL._metrics.clear()
    m.HANDLER_DURATION._metrics.clear()
    m.PERMANENT_ERRORS_LAST_MINUTE._events.clear()
    m.TEMPORARY_ERRORS_LAST_MINUTE._events.clear()
    yield


def _sample(metric, **labels):
    return metric.labels(**labels)._value.get()


def _window_count(collector, handler):
    return collector._purge_and_count().get(handler, 0)


# ---------------------------------------------------------------------------
# track_handler context manager
# ---------------------------------------------------------------------------

def test_track_handler_records_success():
    from my_operator.metrics import track_handler, EVENTS_TOTAL

    with track_handler('create'):
        pass

    assert _sample(EVENTS_TOTAL, handler='create', status='success') == 1.0


def test_track_handler_records_duration():
    from my_operator.metrics import track_handler, HANDLER_DURATION

    with track_handler('update'):
        pass

    assert HANDLER_DURATION.labels(handler='update')._sum.get() >= 0


def test_track_handler_records_permanent_error():
    from my_operator.metrics import track_handler, PERMANENT_ERRORS_LAST_MINUTE

    with pytest.raises(kopf.PermanentError):
        with track_handler('create'):
            raise kopf.PermanentError("bad spec")

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'create') == 1


def test_track_handler_records_temporary_error():
    from my_operator.metrics import track_handler, TEMPORARY_ERRORS_LAST_MINUTE

    with pytest.raises(kopf.TemporaryError):
        with track_handler('update'):
            raise kopf.TemporaryError("api down")

    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'update') == 1


def test_track_handler_does_not_record_permanent_on_temporary():
    from my_operator.metrics import track_handler, PERMANENT_ERRORS_LAST_MINUTE

    with pytest.raises(kopf.TemporaryError):
        with track_handler('delete'):
            raise kopf.TemporaryError("transient")

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'delete') == 0


def test_track_handler_does_not_record_temporary_on_permanent():
    from my_operator.metrics import track_handler, TEMPORARY_ERRORS_LAST_MINUTE

    with pytest.raises(kopf.PermanentError):
        with track_handler('create'):
            raise kopf.PermanentError("fatal")

    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'create') == 0


def test_window_collector_purges_old_events():
    import time
    from my_operator.metrics import _SlidingWindowCollector

    collector = _SlidingWindowCollector('test_metric', 'test', window_seconds=1)
    collector._events.append((time.monotonic() - 2, 'create'))  # already expired
    collector.record('create')                                   # fresh event

    assert collector._purge_and_count().get('create') == 1


def test_window_collector_describe_yields_gauge_family():
    from my_operator.metrics import _SlidingWindowCollector

    collector = _SlidingWindowCollector('test_describe', 'A description', window_seconds=60)
    families = list(collector.describe())

    assert len(families) == 1
    assert families[0].name == 'test_describe'


def test_window_collector_collect_yields_label_samples():
    from my_operator.metrics import _SlidingWindowCollector

    collector = _SlidingWindowCollector('test_collect', 'A description', window_seconds=60)
    collector.record('create')
    collector.record('create')
    collector.record('delete')

    families = list(collector.collect())
    assert len(families) == 1
    samples = {s.labels['handler']: s.value for s in families[0].samples}
    assert samples['create'] == 2
    assert samples['delete'] == 1


def test_start_metrics_starts_http_server(mocker, logger):
    from my_operator.config import METRICS_PORT
    from my_operator.metrics import start_metrics
    mock_server = mocker.patch('my_operator.metrics.start_http_server')

    start_metrics(logger)

    mock_server.assert_called_once_with(METRICS_PORT)


def test_track_handler_generic_exception_records_error_event():
    from my_operator.metrics import track_handler, EVENTS_TOTAL

    with pytest.raises(RuntimeError):
        with track_handler('create'):
            raise RuntimeError("unexpected failure")

    assert _sample(EVENTS_TOTAL, handler='create', status='error') == 1.0


def test_track_handler_generic_exception_not_recorded_in_windows():
    from my_operator.metrics import (
        track_handler, PERMANENT_ERRORS_LAST_MINUTE, TEMPORARY_ERRORS_LAST_MINUTE,
    )

    with pytest.raises(RuntimeError):
        with track_handler('delete'):
            raise RuntimeError("unexpected")

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'delete') == 0
    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'delete') == 0


# ---------------------------------------------------------------------------
# Create handler
# ---------------------------------------------------------------------------

def test_create_increments_active_webapps(mock_k8s_client, mocker, logger):
    import my_operator.metrics as m
    mocker.patch('kopf.adopt')

    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=MagicMock())

    assert m.ACTIVE_WEBAPPS._value.get() == 1.0


def test_create_records_success_event(mock_k8s_client, mocker, logger):
    from my_operator.metrics import EVENTS_TOTAL
    mocker.patch('kopf.adopt')

    on_create(spec=SPEC, name='test-app', namespace='default',
              logger=logger, patch=MagicMock())

    assert _sample(EVENTS_TOTAL, handler='create', status='success') == 1.0


def test_create_permanent_error_recorded_in_window(mock_k8s_client, mocker, logger):
    from my_operator.metrics import PERMANENT_ERRORS_LAST_MINUTE
    mocker.patch('kopf.adopt')

    with pytest.raises(kopf.PermanentError):
        on_create(spec={'image': 'nginx'}, name='test-app', namespace='default',
                  logger=logger, patch=MagicMock())

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'create') == 1


def test_create_temporary_error_recorded_in_window(mock_k8s_client, mocker, logger):
    from my_operator.metrics import TEMPORARY_ERRORS_LAST_MINUTE
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=MagicMock())

    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'create') == 1


def test_create_does_not_increment_active_webapps_on_error(
        mock_k8s_client, mocker, logger):
    import my_operator.metrics as m
    mocker.patch('kopf.adopt')
    mock_k8s_client['apps'].create_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        on_create(spec=SPEC, name='test-app', namespace='default',
                  logger=logger, patch=MagicMock())

    assert m.ACTIVE_WEBAPPS._value.get() == 0.0


# ---------------------------------------------------------------------------
# Update handler
# ---------------------------------------------------------------------------

def test_update_records_success_event(mock_k8s_client, logger):
    from my_operator.metrics import EVENTS_TOTAL

    on_update(spec=NEW_SPEC, old=OLD_SPEC, new=NEW_SPEC,
              name='test-app', namespace='default',
              logger=logger, patch=MagicMock())

    assert _sample(EVENTS_TOTAL, handler='update', status='success') == 1.0


def test_update_temporary_error_recorded_in_window(mock_k8s_client, logger):
    from my_operator.metrics import TEMPORARY_ERRORS_LAST_MINUTE
    mock_k8s_client['apps'].patch_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        on_update(spec=NEW_SPEC, old=OLD_SPEC, new=NEW_SPEC,
                  name='test-app', namespace='default',
                  logger=logger, patch=MagicMock())

    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'update') == 1


def test_update_permanent_error_recorded_in_window(mock_k8s_client, logger):
    from my_operator.metrics import PERMANENT_ERRORS_LAST_MINUTE
    mock_k8s_client['apps'].patch_namespaced_deployment.side_effect = ApiException(status=403)

    with pytest.raises(kopf.PermanentError):
        on_update(spec=NEW_SPEC, old=OLD_SPEC, new=NEW_SPEC,
                  name='test-app', namespace='default',
                  logger=logger, patch=MagicMock())

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'update') == 1


# ---------------------------------------------------------------------------
# Delete handler
# ---------------------------------------------------------------------------

def test_delete_decrements_active_webapps(mock_k8s_client, logger):
    import my_operator.metrics as m
    m.ACTIVE_WEBAPPS._value.set(1)

    on_delete(name='test-app', namespace='default', logger=logger)

    assert m.ACTIVE_WEBAPPS._value.get() == 0.0


def test_delete_records_success_event(mock_k8s_client, logger):
    from my_operator.metrics import EVENTS_TOTAL

    on_delete(name='test-app', namespace='default', logger=logger)

    assert _sample(EVENTS_TOTAL, handler='delete', status='success') == 1.0


def test_delete_temporary_error_recorded_in_window(mock_k8s_client, logger):
    from my_operator.metrics import TEMPORARY_ERRORS_LAST_MINUTE
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        on_delete(name='test-app', namespace='default', logger=logger)

    assert _window_count(TEMPORARY_ERRORS_LAST_MINUTE, 'delete') == 1


def test_delete_permanent_error_recorded_in_window(mock_k8s_client, logger):
    from my_operator.metrics import PERMANENT_ERRORS_LAST_MINUTE
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=403)

    with pytest.raises(kopf.PermanentError):
        on_delete(name='test-app', namespace='default', logger=logger)

    assert _window_count(PERMANENT_ERRORS_LAST_MINUTE, 'delete') == 1


def test_delete_does_not_decrement_active_webapps_on_error(
        mock_k8s_client, logger):
    import my_operator.metrics as m
    m.ACTIVE_WEBAPPS._value.set(1)
    mock_k8s_client['apps'].delete_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(kopf.TemporaryError):
        on_delete(name='test-app', namespace='default', logger=logger)

    assert m.ACTIVE_WEBAPPS._value.get() == 1.0
