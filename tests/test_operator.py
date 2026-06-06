import logging


def test_on_startup_calls_start_metrics(mocker):
    mock_start = mocker.patch('my_operator.metrics.start_metrics')
    from my_operator.operator import on_startup

    logger = logging.getLogger('my_operator.test')
    on_startup(logger=logger)

    mock_start.assert_called_once_with(logger)
