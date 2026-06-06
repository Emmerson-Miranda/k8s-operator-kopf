import kopf

from my_operator.handlers import create, update, delete  # noqa: F401
from my_operator.metrics import start_metrics


@kopf.on.startup()
def on_startup(logger, **kwargs):
    start_metrics(logger)
