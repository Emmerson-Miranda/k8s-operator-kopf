import time
import threading
from collections import deque
from contextlib import contextmanager

import kopf
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

from my_operator.config import METRICS_PORT, ERROR_WINDOW_SECONDS

EVENTS_TOTAL = Counter(
    'webapp_events_total',
    'Total WebApp handler invocations',
    ['handler', 'status'],
)

HANDLER_DURATION = Histogram(
    'webapp_handler_duration_seconds',
    'WebApp handler execution time in seconds',
    ['handler'],
)

ACTIVE_WEBAPPS = Gauge(
    'webapp_active_total',
    'Number of active WebApp resources managed by the operator',
)


class _SlidingWindowCollector:
    """Exposes a Gauge counting events within a rolling time window."""

    def __init__(self, metric_name, description, window_seconds):
        self._name = metric_name
        self._description = description
        self._window = window_seconds
        self._events = deque()   # (monotonic_timestamp, handler)
        self._lock = threading.Lock()

    def record(self, handler):
        with self._lock:
            self._events.append((time.monotonic(), handler))

    def _purge_and_count(self):
        cutoff = time.monotonic() - self._window
        with self._lock:
            while self._events and self._events[0][0] < cutoff:
                self._events.popleft()
            counts = {}
            for _, handler in self._events:
                counts[handler] = counts.get(handler, 0) + 1
        return counts

    def describe(self):
        yield GaugeMetricFamily(self._name, self._description, labels=['handler'])

    def collect(self):
        metric = GaugeMetricFamily(self._name, self._description, labels=['handler'])
        for handler, count in self._purge_and_count().items():
            metric.add_metric([handler], count)
        yield metric


PERMANENT_ERRORS_LAST_MINUTE = _SlidingWindowCollector(
    'webapp_permanent_errors_last_minute',
    f'WebApp PermanentError count in the last {ERROR_WINDOW_SECONDS}s',
    ERROR_WINDOW_SECONDS,
)

TEMPORARY_ERRORS_LAST_MINUTE = _SlidingWindowCollector(
    'webapp_temporary_errors_last_minute',
    f'WebApp TemporaryError count in the last {ERROR_WINDOW_SECONDS}s',
    ERROR_WINDOW_SECONDS,
)

REGISTRY.register(PERMANENT_ERRORS_LAST_MINUTE)
REGISTRY.register(TEMPORARY_ERRORS_LAST_MINUTE)


def start_metrics(logger):
    start_http_server(METRICS_PORT)
    logger.info(f"Metrics server listening on :{METRICS_PORT}/metrics")


@contextmanager
def track_handler(name):
    start = time.monotonic()
    status = 'success'
    try:
        yield
    except kopf.PermanentError:
        status = 'error'
        PERMANENT_ERRORS_LAST_MINUTE.record(name)
        raise
    except kopf.TemporaryError:
        status = 'error'
        TEMPORARY_ERRORS_LAST_MINUTE.record(name)
        raise
    except Exception:
        status = 'error'
        raise
    finally:
        HANDLER_DURATION.labels(handler=name).observe(time.monotonic() - start)
        EVENTS_TOTAL.labels(handler=name, status=status).inc()
