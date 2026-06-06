import kopf
import kubernetes
from kubernetes.client.exceptions import ApiException

from my_operator.config import (
    OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
    HTTP_NOT_FOUND, HTTP_TOO_MANY_REQUESTS, HTTP_SERVER_ERROR,
    RETRY_DELAY, MAX_RETRIES, RETRY_BACKOFF,
)


@kopf.on.delete(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
                retries=MAX_RETRIES, backoff=RETRY_BACKOFF)
def on_delete(name, namespace, logger, **kwargs):
    logger.info(f"[DELETE] Starting name={name} ns={namespace}")
    apps_v1 = kubernetes.client.AppsV1Api()
    core_v1 = kubernetes.client.CoreV1Api()

    try:
        apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
        logger.info(f"Deleted Deployment {name}")
    except ApiException as e:
        if e.status == HTTP_NOT_FOUND:
            logger.warning(f"Deployment {name} already gone, skipping")
        elif e.status == HTTP_TOO_MANY_REQUESTS or e.status >= HTTP_SERVER_ERROR:
            logger.info(f"[DELETE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Transient error deleting Deployment: {e}", delay=RETRY_DELAY)
        else:
            logger.info(f"[DELETE] PermanentError name={name} ns={namespace}")
            raise kopf.PermanentError(f"Failed to delete Deployment: {e}")

    try:
        core_v1.delete_namespaced_service(name=name, namespace=namespace)
        logger.info(f"Deleted Service {name}")
    except ApiException as e:
        if e.status == HTTP_NOT_FOUND:
            logger.warning(f"Service {name} already gone, skipping")
        elif e.status == HTTP_TOO_MANY_REQUESTS or e.status >= HTTP_SERVER_ERROR:
            logger.info(f"[DELETE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Transient error deleting Service: {e}", delay=RETRY_DELAY)
        else:
            logger.info(f"[DELETE] PermanentError name={name} ns={namespace}")
            raise kopf.PermanentError(f"Failed to delete Service: {e}")

    logger.info(f"[DELETE] Completed name={name} ns={namespace}")
