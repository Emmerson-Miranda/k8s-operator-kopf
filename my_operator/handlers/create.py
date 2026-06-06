import kopf
import kubernetes
from kubernetes.client.exceptions import ApiException

from my_operator.config import (
    OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
    SERVICE_TYPE, HTTP_CONFLICT, HTTP_TOO_MANY_REQUESTS, HTTP_SERVER_ERROR,
    RETRY_DELAY, MAX_RETRIES, RETRY_BACKOFF,
)


@kopf.on.create(OPERATOR_GROUP, OPERATOR_VERSION, OPERATOR_PLURAL,
                retries=MAX_RETRIES, backoff=RETRY_BACKOFF)
def on_create(spec, name, namespace, logger, patch, **kwargs):
    logger.info(f"[CREATE] Starting name={name} ns={namespace} spec={spec}")

    try:
        image = spec['image']
        replicas = spec['replicas']
        port = spec['port']
    except KeyError as e:
        patch.status['message'] = f"Error: missing spec field {e}"
        logger.info(f"[CREATE] PermanentError name={name} ns={namespace}")
        raise kopf.PermanentError(f"Missing required spec field: {e}")

    apps_v1 = kubernetes.client.AppsV1Api()
    core_v1 = kubernetes.client.CoreV1Api()

    deployment = kubernetes.client.V1Deployment(
        metadata=kubernetes.client.V1ObjectMeta(name=name, namespace=namespace),
        spec=kubernetes.client.V1DeploymentSpec(
            replicas=replicas,
            selector=kubernetes.client.V1LabelSelector(match_labels={'app': name}),
            template=kubernetes.client.V1PodTemplateSpec(
                metadata=kubernetes.client.V1ObjectMeta(labels={'app': name}),
                spec=kubernetes.client.V1PodSpec(
                    containers=[
                        kubernetes.client.V1Container(
                            name=name,
                            image=image,
                            ports=[kubernetes.client.V1ContainerPort(container_port=port)],
                        )
                    ]
                ),
            ),
        ),
    )
    kopf.adopt(deployment)

    try:
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
    except ApiException as e:
        if e.status == HTTP_CONFLICT:
            logger.warning(f"Deployment {name} already exists, skipping create")
        elif e.status == HTTP_TOO_MANY_REQUESTS or e.status >= HTTP_SERVER_ERROR:
            patch.status['message'] = f"Error: transient failure creating Deployment ({e.status})"
            logger.info(f"[CREATE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Transient error creating Deployment: {e}", delay=RETRY_DELAY)
        else:
            patch.status['message'] = f"Error: failed to create Deployment ({e.status})"
            logger.info(f"[CREATE] PermanentError name={name} ns={namespace}")
            raise kopf.PermanentError(f"Failed to create Deployment: {e}")

    service = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(name=name, namespace=namespace),
        spec=kubernetes.client.V1ServiceSpec(
            selector={'app': name},
            ports=[kubernetes.client.V1ServicePort(port=port, target_port=port)],
            type=SERVICE_TYPE,
        ),
    )
    kopf.adopt(service)

    try:
        core_v1.create_namespaced_service(namespace=namespace, body=service)
    except ApiException as e:
        if e.status == HTTP_CONFLICT:
            logger.warning(f"Service {name} already exists, skipping create")
        elif e.status == HTTP_TOO_MANY_REQUESTS or e.status >= HTTP_SERVER_ERROR:
            patch.status['message'] = f"Error: transient failure creating Service ({e.status})"
            logger.info(f"[CREATE] TemporaryError name={name} ns={namespace}")
            raise kopf.TemporaryError(f"Transient error creating Service: {e}", delay=RETRY_DELAY)
        else:
            patch.status['message'] = f"Error: failed to create Service ({e.status})"
            logger.info(f"[CREATE] PermanentError name={name} ns={namespace}")
            raise kopf.PermanentError(f"Failed to create Service: {e}")

    patch.status['message'] = 'Provisioned'
    logger.info(f"[CREATE] Completed name={name} ns={namespace} image={image} replicas={replicas} port={port}")
