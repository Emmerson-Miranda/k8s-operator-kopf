import kopf
import kubernetes


@kopf.on.update('demo.example.com', 'v1', 'webapps', field='spec')
def on_update(spec, old, new, name, namespace, logger, patch, **kwargs):
    logger.info(f"[UPDATE] Starting{name} ns={namespace}")
    apps_v1 = kubernetes.client.AppsV1Api()

    # old/new are the field values (spec dict) when field= is specified
    patch_body = {'spec': {}}

    if old.get('replicas') != new.get('replicas'):
        patch_body['spec']['replicas'] = new['replicas']

    if old.get('image') != new.get('image'):
        patch_body['spec'].setdefault('template', {})
        patch_body['spec']['template'] = {
            'spec': {
                'containers': [{'name': name, 'image': new['image']}]
            }
        }

    if patch_body['spec']:
        apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=patch_body)
        logger.info(f"WebApp {name} deployment updated: {list(patch_body['spec'].keys())}")

    patch.status['message'] = 'Updated'

    logger.info(f"[UPDATE] Completed{name} ns={namespace}")
