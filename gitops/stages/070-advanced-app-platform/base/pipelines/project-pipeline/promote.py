"""Publish a validated runtime artifact and immutable image digest to its registered GitLab repository."""
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

DIGEST = re.compile(r'^image-registry\.openshift-image-registry\.svc:5000/([a-z0-9-]+)/([a-z0-9-]+)@sha256:[0-9a-f]{64}$')
KINDS = {'Deployment': 'apps/v1', 'Service': 'v1', 'Route': 'route.openshift.io/v1', 'PersistentVolumeClaim': 'v1', 'ConfigMap': 'v1'}


def validate_runtime(objects, name, namespace, image):
    match = DIGEST.fullmatch(image)
    if not match or match.groups() != (namespace, name):
        raise ValueError('Image is not this project internal registry digest')
    found = 0
    result = []
    for original in objects:
        obj = json.loads(json.dumps(original))
        meta = obj['metadata']; kind = obj['kind']
        if kind not in KINDS or obj['apiVersion'] != KINDS[kind]:
            raise ValueError('Runtime kind is not allowed: ' + kind)
        if meta.get('namespace', namespace) != namespace or not (meta['name'] == name or meta['name'].startswith(name + '-')):
            raise ValueError('Runtime resource belongs to another project')
        if meta.get('ownerReferences') or meta.get('finalizers'):
            raise ValueError('Application cannot grant lifecycle authority')
        meta['namespace'] = namespace
        meta.pop('creationTimestamp', None)
        obj.pop('status', None)
        if kind == 'Service' and obj['spec'].get('type', 'ClusterIP') != 'ClusterIP':
            raise ValueError('Application service must be ClusterIP')
        if kind == 'Route':
            spec = obj['spec']
            if spec.get('host') or spec.get('wildcardPolicy', 'None') != 'None' or spec.get('alternateBackends'):
                raise ValueError('Application cannot claim a host or foreign backend')
            if spec['to'].get('name') != name:
                raise ValueError('Route must target this application service')
        if kind == 'Deployment':
            pod = obj['spec']['template']['spec']
            if any(pod.get(k) for k in ('hostNetwork', 'hostPID', 'hostIPC', 'nodeName', 'initContainers')):
                raise ValueError('Runtime pod requests forbidden host or initialization authority')
            if pod.get('serviceAccountName') not in (None, 'app-runtime'):
                raise ValueError('Runtime pod requests another service account')
            if pod.get('imagePullSecrets'):
                raise ValueError('Runtime cannot mount delivery credentials as image-pull secrets')
            pod['serviceAccountName'] = 'app-runtime'; pod['automountServiceAccountToken'] = False
            pod['securityContext'] = {'runAsNonRoot': True, 'seccompProfile': {'type': 'RuntimeDefault'}}
            for volume in pod.get('volumes', []):
                if not set(volume).issubset({'name', 'emptyDir', 'persistentVolumeClaim', 'configMap'}):
                    raise ValueError('Runtime volume requests host data or a secret')
            for container in pod['containers']:
                if any('secretRef' in entry for entry in container.get('envFrom', [])):
                    raise ValueError('Runtime cannot consume arbitrary Secret envFrom')
                sec = container.get('securityContext', {})
                if sec.get('privileged') or sec.get('allowPrivilegeEscalation') or sec.get('runAsUser') == 0 or sec.get('capabilities', {}).get('add'):
                    raise ValueError('Runtime container requests elevated privileges')
                container['securityContext'] = {'runAsNonRoot': True, 'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}}
                if meta['name'] == name and container.get('name') == name:
                    container['image'] = image; found += 1
                elif '@sha256:' not in container['image']:
                    raise ValueError('Supporting containers require immutable images')
                for env in container.get('env', []):
                    if 'secretKeyRef' in env.get('valueFrom', {}):
                        if env['valueFrom']['secretKeyRef']['name'] != name + '-app-db':
                            raise ValueError('Runtime can reference only its platform-owned application database secret')
        result.append(obj)
    if found != 1:
        raise ValueError('Runtime artifact must contain exactly one application container')
    return result


def main():
    config = json.loads(Path('/config/delivery.json').read_text())
    name, ns = config['repo_name'], os.environ['NAMESPACE']
    sha, image = os.environ['SOURCE_COMMIT'], os.environ['IMAGE']
    if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('Source commit is not immutable')
    root = Path(os.environ['SOURCE_DIR'])
    directory = root / ('k8s-run' if (root / 'k8s-run').is_dir() else 'k8s')
    if not directory.is_dir() or directory.is_symlink(): raise ValueError('Runtime artifact directory missing or redirected')
    for file in directory.rglob('*'):
        if file.is_symlink(): raise ValueError('Runtime artifacts must not contain symbolic links')
    output = subprocess.check_output(['oc', 'create', '--dry-run=client', '-f', str(directory), '-o', 'json'], universal_newlines=True)
    decoded = json.loads(output)
    objects = validate_runtime(decoded.get('items', [decoded]), name, ns, image)
    token = Path('/credentials/token').read_text().strip()
    base = config['gitlab_base_url'].rstrip('/')

    def api(method, project, path, data=None):
        request = urllib.request.Request(base + '/api/v4/projects/' + str(project) + '/' + path,
            None if data is None else json.dumps(data).encode(), {'PRIVATE-TOKEN': token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(request, timeout=30) as response: return json.load(response)

    project = config['delivery_project_id']
    remote = api('GET', project, 'repository/files/promotion.json?ref=main')
    import base64
    previous = json.loads(base64.b64decode(remote['content']))
    if previous.get('source_commit'):
        if previous['source_commit'] == sha:
            if previous['image'] != image: raise ValueError('Same source identity cannot promote a different image')
            commit = previous['deployment_commit'] if previous.get('deployment_commit') else remote['last_commit_id']
        else:
            # The clone Task retains full source history. An older or diverged build cannot roll back delivery.
            subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', previous['source_commit'], sha], check=True)
            commit = None
    else: commit = None
    if commit is None:
        record = {'source_commit': sha, 'image': image, 'source_project_id': config['source_project_id']}
        actions = [{'action': 'update', 'file_path': 'promotion.json', 'content': json.dumps(record, sort_keys=True), 'last_commit_id': remote['last_commit_id']}]
        artifact = api('GET', project, 'repository/files/runtime.json?ref=main')
        actions.append({'action': 'update', 'file_path': 'runtime.json', 'content': json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects}, sort_keys=True), 'last_commit_id': artifact['last_commit_id']})
        commit = api('POST', project, 'repository/commits', {'branch': 'main', 'commit_message': 'deploy: ' + name + ' ' + sha[:12], 'actions': actions})['id']
    argo_token = Path('/argo/token').read_text().strip()
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        request = urllib.request.Request(config['argocd_url'] + '/api/v1/applications/' + quote('runtime-' + name), headers={'Authorization': 'Bearer ' + argo_token})
        with urllib.request.urlopen(request, timeout=30) as response: app = json.load(response)
        status = app.get('status', {})
        if status.get('sync', {}).get('revision') == commit and status['sync']['status'] == 'Synced' and status.get('health', {}).get('status') == 'Healthy':
            deployed = json.loads(subprocess.check_output(['oc', 'get', 'deployment', name, '-n', ns, '-o', 'json'], universal_newlines=True))
            containers = deployed['spec']['template']['spec']['containers']
            if any(c['name'] == name and c['image'] == image for c in containers) and deployed.get('status', {}).get('availableReplicas', 0) >= 1:
                Path(os.environ['RESULT_PATH']).write_text(commit)
                print('GitOps deployment verified:', sha, commit)
                return
        time.sleep(10)
    raise RuntimeError('GitOps did not converge on this deployment commit and image digest')


if __name__ == '__main__': main()
