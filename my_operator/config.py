import os
from http import HTTPStatus

OPERATOR_GROUP = os.getenv('OPERATOR_GROUP', 'demo.example.com')
OPERATOR_VERSION = os.getenv('OPERATOR_VERSION', 'v1')
OPERATOR_PLURAL = os.getenv('OPERATOR_PLURAL', 'webapps')
SERVICE_TYPE = os.getenv('SERVICE_TYPE', 'ClusterIP')
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '10'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '10'))
RETRY_BACKOFF = int(os.getenv('RETRY_BACKOFF', '60'))

# Named HTTP status aliases used across handlers
HTTP_NOT_FOUND = HTTPStatus.NOT_FOUND.value              # 404
HTTP_CONFLICT = HTTPStatus.CONFLICT.value               # 409
HTTP_TOO_MANY_REQUESTS = HTTPStatus.TOO_MANY_REQUESTS.value  # 429
HTTP_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR.value  # 500
