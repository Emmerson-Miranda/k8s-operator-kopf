import kopf
import kubernetes
from kubernetes.client.exceptions import ApiException

from my_operator.config import (
    OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
    HTTP_NOT_FOUND, HTTP_SERVER_ERROR,
    RETRY_DELAY, MAX_RETRIES, RETRY_BACKOFF,
)


@kopf.on.update(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL, field='spec',
                retries=MAX_RETRIES, backoff=RETRY_BACKOFF)
def on_update(spec, old, new, name, namespace, logger, patch, **kwargs):
    logger.info(f"[UPDATE] Starting name={name} ns={namespace}")
    apps_v1 = kubernetes.client.AppsV1Api()

    patch_body = {'spec': {}}

    if old.get('replicas') != new.get('replicas'):
        patch_body['spec']['replicas'] = new['replicas']

    if old.get('image') != new.get('image'):
        patch_body['spec']['template'] = {
            'spec': {
                'containers': [{'name': name, 'image': new['image']}]
            }
        }

    if not patch_body['spec']:
        logger.info(f"[UPDATE] No relevant changes for name={name}, skipping")
        return

    try:
        apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=patch_body)
        logger.info(f"Deployment {name} updated: {list(patch_body['spec'].keys())}")
    except ApiException as e:
        if e.status == HTTP_NOT_FOUND:
            patch.status['message'] = "Error: Deployment not found"
            logger.info(f"[UPDATE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Deployment {name} not found, will retry", delay=RETRY_DELAY)
        elif e.status >= HTTP_SERVER_ERROR:
            patch.status['message'] = f"Error: transient failure updating Deployment ({e.status})"
            logger.info(f"[UPDATE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Transient error updating Deployment: {e}", delay=RETRY_DELAY)
        else:
            patch.status['message'] = f"Error: failed to update Deployment ({e.status})"
            logger.info(f"[UPDATE] PermanentError name={name} ns={namespace}")
            raise kopf.PermanentError(f"Failed to update Deployment: {e}")

    patch.status['message'] = 'Updated'
    logger.info(f"[UPDATE] Completed name={name} ns={namespace}")
