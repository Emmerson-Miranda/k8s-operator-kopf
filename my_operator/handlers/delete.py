import kopf
import kubernetes
from kubernetes.client.exceptions import ApiException


@kopf.on.delete('demo.example.com', 'v1', 'webapps')
def on_delete(name, namespace, logger, **kwargs):
    logger.info(f"[DELETE] Starting{name} ns={namespace}")
    apps_v1 = kubernetes.client.AppsV1Api()
    core_v1 = kubernetes.client.CoreV1Api()

    try:
        apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
        logger.info(f"Deleted Deployment {name}")
    except ApiException as e:
        if e.status != 404:
            raise

    try:
        core_v1.delete_namespaced_service(name=name, namespace=namespace)
        logger.info(f"Deleted Service {name}")
    except ApiException as e:
        if e.status != 404:
            raise
        
    logger.info(f"[DELETE] Completed{name} ns={namespace}")

