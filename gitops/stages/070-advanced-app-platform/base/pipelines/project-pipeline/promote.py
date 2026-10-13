"""Publish a validated runtime artifact and immutable image digest to its registered GitLab repository."""
import json
import os
import re
import subprocess
import tempfile
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
            if spec.get('host') or spec.get('subdomain') or spec.get('wildcardPolicy', 'None') != 'None' or spec.get('alternateBackends'):
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


def clean_git(directory, repository, credential_file):
    if not re.fullmatch(r'https://gitlab\.[a-z0-9.-]+/rhoai-workloads/[a-z0-9-]+\.git', repository):
        raise ValueError('Promotion source is not a registered private workload repository')
    env = {key: os.environ[key] for key in ('PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if key in os.environ}
    env.update(HOME=str(directory), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    argv = ['git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null',
            '-c', 'protocol.file.allow=never', '-c', 'credential.helper=store --file=' + str(credential_file),
            '-C', str(directory)]
    def git(*args):
        return subprocess.check_output(argv + list(args), env=env, stderr=subprocess.PIPE)
    git('init', '--bare', '.')
    git('remote', 'add', 'origin', repository)
    return git


def committed_artifacts(git, sha, directory):
    rows = git('ls-tree', '-r', '-z', sha, '--', 'k8s-run', 'k8s').split(b'\0')
    files = []
    for row in rows:
        if not row: continue
        header, name = row.split(b'\t', 1)
        mode, kind, _digest = header.split()
        path = name.decode('utf-8')
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('Runtime artifacts cannot contain links or submodules')
        if '..' in Path(path).parts: raise ValueError('Unsafe committed artifact path')
        files.append(path)
    prefix = 'k8s-run/' if any(p.startswith('k8s-run/') for p in files) else 'k8s/'
    selected = [p for p in files if p.startswith(prefix)]
    if not selected: raise ValueError('No runtime artifacts at the requested source commit')
    for index, path in enumerate(selected):
        if Path(path).suffix not in ('.yaml', '.yml', '.json'): continue
        (directory / (str(index) + Path(path).suffix)).write_bytes(git('show', sha + ':' + path))
    if not list(directory.iterdir()): raise ValueError('No declarative runtime artifacts')


def main():
    config = json.loads(Path('/config/delivery.json').read_text())
    name, ns = config['repo_name'], os.environ['NAMESPACE']
    sha, image = os.environ['SOURCE_COMMIT'], os.environ['IMAGE']
    if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('Source commit is not immutable')
    # This Task never mounts the build workspace. Its fresh repository and Git
    # configuration cannot inherit developer-written refs, grafts or hooks.
    temporary = tempfile.TemporaryDirectory(prefix='promotion-')
    root = Path(temporary.name)
    git = clean_git(root, config['source_repo'], Path('/source-credentials/.git-credentials'))
    git('fetch', '--no-tags', 'origin', sha)
    if git('rev-parse', sha + '^{commit}').decode().strip() != sha:
        raise ValueError('Fetched source does not match the requested commit')
    directory = root / 'artifacts'; directory.mkdir()
    committed_artifacts(git, sha, directory)
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
            git('merge-base', '--is-ancestor', previous['source_commit'], sha)
            commit = None
    else: commit = None
    if commit is None:
        record = {'source_commit': sha, 'image': image, 'source_project_id': config['source_project_id']}
        actions = [{'action': 'update', 'file_path': 'promotion.json', 'content': json.dumps(record, sort_keys=True), 'last_commit_id': remote['last_commit_id']}]
        artifact = api('GET', project, 'repository/files/runtime.json?ref=main')
        actions.append({'action': 'update', 'file_path': 'runtime.json', 'content': json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects}, sort_keys=True), 'last_commit_id': artifact['last_commit_id']})
        commit = api('POST', project, 'repository/commits', {'branch': 'main', 'commit_message': 'deploy: ' + name + ' ' + sha[:12], 'actions': actions})['id']
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        app = json.loads(subprocess.check_output(['oc', 'get', 'application', 'runtime-' + name,
                         '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True))
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
