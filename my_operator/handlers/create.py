import kopf
import kubernetes


@kopf.on.create('demo.example.com', 'v1', 'webapps')
def on_create(spec, name, namespace, logger, patch, **kwargs):
    logger.info(f"[CREATE] Starting{name} ns={namespace}, spec={spec}")

    image = spec['image']
    replicas = spec['replicas']
    port = spec['port']

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
    apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)

    service = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(name=name, namespace=namespace),
        spec=kubernetes.client.V1ServiceSpec(
            selector={'app': name},
            ports=[kubernetes.client.V1ServicePort(port=port, target_port=port)],
            type='ClusterIP',
        ),
    )
    kopf.adopt(service)
    core_v1.create_namespaced_service(namespace=namespace, body=service)

    patch.status['message'] = 'Provisioned'
    logger.info(f"[CREATE] Completed{name} ns={namespace} with image={image}, replicas={replicas}, port={port}")
