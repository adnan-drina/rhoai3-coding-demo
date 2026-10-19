"""Platform enrollment from publisher-authored GitLab issues, never from push payloads."""
import datetime
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from secret_writer import write_secret
from urllib.parse import quote
from urllib.parse import urlencode

SHA = re.compile(r'^[0-9a-f]{40}$')
NAME = re.compile(r'^[a-z][a-z0-9-]{2,40}$')
SONAR_KEY = 'rhoai3.io/sonar-project-key'
SONAR_TYPE = 'rhoai3.io/sonar-token-type'
SONAR_NAME = 'rhoai3.io/sonar-token-name'


class EnrollmentPending(ValueError):
    """A known native project operation has not reached a terminal state."""


def enrollment_failure(error, created_at, now=None):
    transient = isinstance(error, (EnrollmentPending, TimeoutError))
    if isinstance(error, urllib.error.HTTPError):
        transient = error.code in (408, 429) or 500 <= error.code <= 599
    elif isinstance(error, urllib.error.URLError):
        transient = True
    elif isinstance(error, subprocess.CalledProcessError):
        transient = '(NotFound)' in (error.stderr or '')
    if transient:
        if not created_at:
            return 'refused', 'MISSING_REQUEST_TIME'
        try:
            stamp = re.sub(r'([+-][0-9]{2}):([0-9]{2})$', r'\1\2', created_at.replace('Z', '+0000'))
            try:
                start = datetime.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S.%f%z')
            except ValueError:
                start = datetime.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S%z')
            age = ((now or datetime.datetime.now(datetime.timezone.utc)) - start).total_seconds()
        except (ValueError, TypeError):
            return 'refused', 'INVALID_REQUEST_TIME'
        if age < 0 or age >= 3600:
            return 'refused', 'ENROLLMENT_DEADLINE'
        return 'pending', 'NATIVE_OPERATION_PENDING' if isinstance(error, EnrollmentPending) else 'TRANSIENT_UPSTREAM'
    return 'refused', 'INVALID_REQUEST' if isinstance(error, (ValueError, KeyError)) else 'PLATFORM_COMMAND_REFUSED'



class Sonar:
    def __init__(self, host, token):
        self.host, self.token = host.rstrip('/'), token

    def request(self, method, path, data=None):
        payload = None if data is None else urlencode(data).encode()
        auth = base64.b64encode((self.token + ':').encode()).decode()
        req = urllib.request.Request(self.host + '/api/' + path, payload,
                                     {'Authorization': 'Basic ' + auth}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None


def scanner_binding(secret, name, project_id):
    annotations = secret.get('metadata', {}).get('annotations', {})
    if (annotations.get(SONAR_KEY) != name
            or annotations.get(SONAR_TYPE) != 'PROJECT_ANALYSIS_TOKEN'
            or annotations.get(SONAR_NAME) != 'gitlab-project-' + str(project_id)
            or not all(secret.get('data', {}).get(k) for k in ('host', 'token'))):
        raise ValueError('Scanner credential is not bound to this project analysis token')
    return secret


def sonar_token_project(token):
    project = token.get('project')
    return project.get('key') if isinstance(project, dict) else None


def ensure_project_scanner(name, ns, project_id):
    # Only the platform-pinned bootstrap receives this control credential.
    # Source-controlled Maven and IDE containers receive a project analysis token.
    control = oc('get', 'secret', 'sonarqube-credentials', '-n', 'app-platform-build', '-o', 'json')['data']
    if not control.get('host') or not control.get('token'):
        raise ValueError('Platform Sonar control credential is incomplete')
    host = base64.b64decode(control['host']).decode()
    sonar = Sonar(host, base64.b64decode(control['token']).decode())
    # The control credential is the platform-provisioner user (Create Projects + Execute Analysis), which cannot
    # search projects; create by exact key and accept the key that already exists.
    try:
        sonar.request('POST', 'projects/create', {'project': name, 'name': name, 'visibility': 'private'})
    except urllib.error.HTTPError as error:
        if error.code != 400 or 'already exists' not in error.read().decode('utf-8', 'replace'):
            raise
    token_name = 'gitlab-project-' + str(project_id)
    tokens = sonar.request('GET', 'user_tokens/search')['userTokens']
    match = [t for t in tokens if t['name'] == token_name]
    try:
        stored = oc('get', 'secret', 'sonarqube-credentials', '-n', ns, '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        stored = None
    if stored is not None:
        scanner_binding(stored, name, project_id)
        if (len(match) != 1 or match[0].get('type') != 'PROJECT_ANALYSIS_TOKEN'
                or sonar_token_project(match[0]) != name
                or base64.b64decode(stored['data']['host']).decode() != host
                or not Sonar(host, base64.b64decode(stored['data']['token']).decode()).request(
                    'GET', 'authentication/validate').get('valid')):
            raise ValueError('Stored project token failed verification; preserve it for reconciliation')
        return stored
    if match:
        raise ValueError('Project token exists without its Secret; refuse blind rotation')
    token = sonar.request('POST', 'user_tokens/generate', {
        'name': token_name, 'type': 'PROJECT_ANALYSIS_TOKEN', 'projectKey': name})
    if token.get('type') != 'PROJECT_ANALYSIS_TOKEN' or not token.get('token'):
        raise ValueError('Sonar did not emit a project analysis token')
    emitted = [t for t in sonar.request('GET', 'user_tokens/search')['userTokens'] if t['name'] == token_name]
    if (len(emitted) != 1 or emitted[0].get('type') != 'PROJECT_ANALYSIS_TOKEN'
            or sonar_token_project(emitted[0]) != name):
        raise ValueError('Emitted token metadata is not bound to this Sonar project')
    doc = resource('Secret', 'sonarqube-credentials', ns, {'type': 'Opaque',
        'stringData': {'host': host, 'token': token['token']}}, 'v1')
    doc['metadata']['annotations'] = {SONAR_KEY: name, SONAR_TYPE: 'PROJECT_ANALYSIS_TOKEN', SONAR_NAME: token_name}
    return oc('create', '-f', '-', '-o', 'json', document=doc)


def mount_project_scanner(name, ns, row, project_id):
    source = scanner_binding(oc('get', 'secret', 'sonarqube-credentials', '-n', ns, '-o', 'json'), name, project_id)
    if row['kind'] == 'imported-application':
        targets = [('wksp-ai-developer', 'coolstore-inventory-service'), ('wksp-ai-admin', 'coolstore-inventory-service')]
    else:
        persona = {'user:default/ai-developer': 'wksp-ai-developer', 'user:default/ai-admin': 'wksp-ai-admin'}
        if row.get('requester') not in persona: raise ValueError('No approved workspace persona')
        targets = [(persona[row['requester']], name)]
    for target_ns, workspace in targets:
        secret = resource('Secret', name + '-sonar-credentials', target_ns, {'type': 'Opaque',
            'data': {'SONAR_HOST': source['data']['host'], 'SONAR_TOKEN': source['data']['token']}}, 'v1')
        secret['metadata']['labels'].update({'controller.devfile.io/mount-to-devworkspace': 'true',
                                             'controller.devfile.io/watch-secret': 'true'})
        secret['metadata']['annotations'] = {SONAR_KEY: name, SONAR_TYPE: 'PROJECT_ANALYSIS_TOKEN',
            SONAR_NAME: 'gitlab-project-' + str(project_id), 'controller.devfile.io/mount-as': 'env',
            'controller.devfile.io/mount-to-devworkspace-include': workspace,
            'controller.devfile.io/mount-on-start': 'true'}
        apply(secret)


def oc(*args, document=None):
    result = subprocess.run(['oc', *args], input=None if document is None else json.dumps(document),
                            universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(result.stdout) if result.stdout.strip().startswith('{') else result.stdout.strip()


def apply(document):
    if document.get('kind') == 'Secret':
        return write_secret(document, oc)
    return oc('apply', '-f', '-', '-o', 'json', document=document)


class GitLab:
    def __init__(self, base, token):
        self.base, self.token = base.rstrip('/'), token

    def request(self, method, path, data=None):
        payload = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(self.base + '/api/v4/' + path, payload,
                                     {'PRIVATE-TOKEN': self.token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None


def validate_request(row, project, commit, group_id, import_receipt=None):
    if project.get('archived'):
        raise ValueError('Archived project is retired; refuse resource recreation')
    if not isinstance(row.get('project_id'), int) or row['project_id'] != project['id']:
        raise ValueError('Project identity mismatch')
    if project['namespace']['id'] != group_id:
        raise ValueError('Project is outside the registered workload group')
    if not NAME.fullmatch(project['path']) or project.get('default_branch') != 'main':
        raise ValueError('Invalid project name or default branch')
    if not SHA.fullmatch(row.get('initial_commit', '')) or row['initial_commit'] == '0' * 40:
        raise ValueError('Enrollment requires an immutable initial commit')
    if commit['id'] != row['initial_commit']:
        raise ValueError('Enrollment commit identity mismatch')
    if row.get('kind') == 'imported-application':
        if import_receipt != row or project['path'] != 'coolstore-inventory-service' or row.get('namespace') != 'coolstore-dev':
            raise ValueError('Imported application requires its platform-written seed')
    else:
        if commit.get('parent_ids') != []:
            raise ValueError('Enrollment does not name the repository first commit')
        if row.get('kind') not in ('application', 'migration'):
            raise ValueError('Unsupported enrollment kind')
    return project['path']


def resource(kind, name, ns, spec, api='rbac.authorization.k8s.io/v1'):
    result = {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': ns,
              'labels': {'app.kubernetes.io/part-of': 'developer-platform',
                         'app.kubernetes.io/managed-by': 'argocd', 'demo.rhoai.io/stage': '070'}}, **spec}
    if kind == 'Application':
        result['metadata'].setdefault('annotations', {})['argocd.argoproj.io/compare-options'] = 'ServerSideDiff=true'
    return result


def trigger_resources(name, ns, project_id, repo, sha):
    listener = 'gitlab-listener'
    template = resource('TriggerTemplate', 'gitlab-push', ns, {'spec': {'params': [{'name': 'revision'}], 'resourcetemplates': [pipeline_run(name, ns, project_id, repo, '$(tt.params.revision)')] }}, 'triggers.tekton.dev/v1beta1')
    event = resource('EventListener', 'gitlab', ns, {'spec': {'serviceAccountName': listener, 'triggers': [{
        'name': 'registered-main-push', 'interceptors': [
            {'ref': {'name': 'gitlab'}, 'params': [{'name': 'secretRef', 'value': {'secretName': 'gitlab-webhook', 'secretKey': 'token'}}, {'name': 'eventTypes', 'value': ['Push Hook']}]},
            {'ref': {'name': 'cel'}, 'params': [{'name': 'filter', 'value': f"body.project.id == {project_id} && body.project.git_http_url == '{repo}' && body.ref == 'refs/heads/main' && has(body.checkout_sha) && body.checkout_sha.matches('^[0-9a-f]{{40}}$') && body.checkout_sha != '{'0'*40}'"}]}],
        'bindings': [{'name': 'revision', 'value': '$(body.checkout_sha)'}], 'template': {'ref': 'gitlab-push'}}]}}, 'triggers.tekton.dev/v1beta1')
    route = resource('Route', 'gitlab-webhook', ns, {'spec': {'to': {'kind': 'Service', 'name': 'el-gitlab'}, 'port': {'targetPort': 8080}, 'tls': {'termination': 'edge', 'insecureEdgeTerminationPolicy': 'Redirect'}}}, 'route.openshift.io/v1')
    return [template, event, route]


def pipeline_run(name, ns, project_id, repo, revision):
    # Deterministic name makes duplicate delivery a harmless AlreadyExists, even before the hook returns.
    return resource('PipelineRun', f'gitlab-{project_id}-{revision}', ns, {'spec': {
        'pipelineRef': {'name': 'app-push'}, 'taskRunTemplate': {'serviceAccountName': 'app-builder'},
        'taskRunSpecs': [{'pipelineTaskName': 'build-and-push', 'serviceAccountName': 'image-builder',
            'metadata': {'annotations': {'openshift.io/required-scc': 'nested-container'}},
            'podTemplate': {'hostUsers': False, 'securityContext': {'runAsUser': 1000, 'runAsNonRoot': True,
                'fsGroup': 1000, 'supplementalGroups': [1000], 'seccompProfile': {'type': 'Unconfined'}}}}],
        'params': [{'name': 'repo-url', 'value': repo}, {'name': 'repo-name', 'value': name}, {'name': 'revision', 'value': revision}],
        'workspaces': [{'name': 'source', 'volumeClaimTemplate': {'spec': {'accessModes': ['ReadWriteOnce'], 'storageClassName': 'gp3-csi', 'resources': {'requests': {'storage': '2Gi'}}}}},
                       {'name': 'basic-auth', 'secret': {'secretName': 'gitlab-read-source'}},
                       {'name': 'maven-cache', 'persistentVolumeClaim': {'claimName': 'maven-cache'}}]},
        'metadata': {'name': f'gitlab-{project_id}-{revision}', 'namespace': ns, 'labels': {'backstage.io/kubernetes-id': name}}}, 'tekton.dev/v1')


def ensure_secret(name, ns, data):
    try:
        return oc('get', 'secret', name, '-n', ns, '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr:
            raise
    return oc('create', '-f', '-', '-o', 'json', document=resource('Secret', name, ns, {'type': 'Opaque', 'stringData': data}, 'v1'))


def ensure_delivery_branch(api, project_id, allow_initial_reset):
    """Use GitLab Free's basic branch API, before granting the writer token."""
    path = 'projects/%s/protected_branches' % project_id
    try:
        current = api.request('GET', path + '/main')
    except urllib.error.HTTPError as error:
        if error.code != 404: raise
        current = None
    def valid(row):
        return (row is not None and row.get('allow_force_push') is False
                and len(row.get('push_access_levels',[])) == 1
                and row['push_access_levels'][0].get('access_level') == 30
                and not row['push_access_levels'][0].get('user_id')
                and not row['push_access_levels'][0].get('group_id'))
    if valid(current): return
    if current:
        if not allow_initial_reset:
            raise ValueError('Delivery branch protection changed after writer issuance; reviewed repair required')
        api.request('DELETE', path + '/main')
    api.request('POST', path, {'name':'main', 'push_access_level':30,
                             'merge_access_level':40, 'allow_force_push':False})
    if not valid(api.request('GET', path + '/main')):
        raise ValueError('Delivery writer cannot safely push its protected branch')


def ensure_delivery(api, name, ns, source_project, config, source_repo):
    path = config['GITLAB_DELIVERY_GROUP'] + '/' + name + '-deployment'
    try:
        delivery = api.request('GET', 'projects/' + quote(path, safe=''))
    except urllib.error.HTTPError as error:
        if error.code != 404: raise
        delivery = api.request('POST', 'projects', {'name': name + '-deployment', 'path': name + '-deployment', 'namespace_id': int(config['GITLAB_DELIVERY_GROUP_ID']), 'visibility': 'private', 'initialize_with_readme': False})
        api.request('POST', f"projects/{delivery['id']}/repository/commits", {'branch': 'main', 'commit_message': 'chore: initialize platform-owned runtime artifacts', 'actions': [
            {'action': 'create', 'file_path': 'kustomization.yaml', 'content': 'apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources: [runtime.json]\n'},
            {'action': 'create', 'file_path': 'runtime.json', 'content': json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': []})},
            {'action': 'create', 'file_path': 'promotion.json', 'content': '{}'}]})
    if delivery['namespace']['id'] != int(config['GITLAB_DELIVERY_GROUP_ID']):
        raise ValueError('Delivery repository is not in the platform-owned group')
    try:
        oc('get', 'secret', 'gitlab-delivery-writer', '-n', ns, '-o', 'json')
        writer_exists = True
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        writer_exists = False
    ensure_delivery_branch(api, delivery['id'], allow_initial_reset=not writer_exists)
    if not writer_exists:
        import datetime
        expiry = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
        token = api.request('POST', f"projects/{delivery['id']}/access_tokens", {'name': 'tekton-promoter', 'scopes': ['api'], 'access_level': 30, 'expires_at': expiry})
        ensure_secret('gitlab-delivery-writer', ns, {'token': token['token'], 'expires_at': expiry})
    try:
        clone = oc('get', 'secret', 'gitlab-delivery-reader-' + name, '-n', 'openshift-gitops', '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        clone = {}
    if not clone.get('data'):
        token = api.request('POST', f"projects/{delivery['id']}/deploy_tokens", {'name': 'argocd-reader', 'scopes': ['read_repository']})
        secret = resource('Secret', 'gitlab-delivery-reader-' + name, 'openshift-gitops', {'type': 'Opaque', 'stringData': {'type': 'git', 'url': delivery['http_url_to_repo'], 'username': token['username'], 'password': token['token']}}, 'v1')
        secret['metadata']['labels'] = {'argocd.argoproj.io/secret-type': 'repository'}
        apply(secret)
    apply(resource('ConfigMap', 'project-delivery-config', ns, {'data': {'delivery.json': json.dumps({'repo_name': name, 'source_project_id': source_project, 'source_repo': source_repo, 'delivery_project_id': delivery['id'], 'gitlab_base_url': config['GITLAB_BASE_URL'], 'argocd_url': config['ARGOCD_URL']})}}, 'v1'))
    apply(resource('Application', 'runtime-' + name, 'openshift-gitops', {'spec': {'project': 'runtime-projects', 'source': {'repoURL': delivery['http_url_to_repo'], 'targetRevision': 'main', 'path': '.'}, 'destination': {'server': 'https://kubernetes.default.svc', 'namespace': ns}, 'syncPolicy': {'automated': {'prune': True, 'selfHeal': True}, 'retry': {'limit': 10, 'backoff': {'duration': '5s', 'factor': 2, 'maxDuration': '3m'}}, 'syncOptions': ['RespectIgnoreDifferences=true']}}}, 'argoproj.io/v1alpha1'))


def bootstrap_project(api, row, project, commit, config, import_receipt=None):
    name = validate_request(row, project, commit, int(config['GITLAB_WORKLOAD_GROUP_ID']), import_receipt)
    ns = row['namespace'] if import_receipt is not None else name + '-dev'
    repo = project['http_url_to_repo']
    if os.environ.get('POD_NAMESPACE') != ns:
        raise ValueError('Project bootstrap is outside its own namespace')
    registration = {'project_id': project['id'], 'repo_url': repo, 'initial_commit': row['initial_commit'], 'kind': row['kind']}
    try:
        old = oc('get', 'configmap', 'project-registration', '-n', ns, '-o', 'json')['data']['registration.json']
        if json.loads(old) != registration:
            raise ValueError('Registration identity changed; refuse to transfer project authority')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr:
            raise
        oc('create', '-f', '-', document=resource('ConfigMap', 'project-registration', ns, {'immutable': True, 'data': {'registration.json': json.dumps(registration)}}, 'v1'))
    # Read-only deploy token, never the publisher or enrollment token.
    try:
        oc('get', 'secret', 'gitlab-read-source', '-n', ns, '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        token = api.request('POST', f"projects/{project['id']}/deploy_tokens", {'name': 'tekton-read-' + name, 'scopes': ['read_repository']})
        host = config['GITLAB_HOST']
        ensure_secret('gitlab-read-source', ns, {'.git-credentials': f"https://{token['username']}:{quote(token['token'], safe='')}@{host}", '.gitconfig': '[credential]\n  helper = store\n'})
    hook = ensure_secret('gitlab-webhook', ns, {'token': secrets.token_urlsafe(32)})
    for obj in trigger_resources(name, ns, project['id'], repo, row['initial_commit']):
        if obj['kind'] in ('TriggerTemplate', 'EventListener', 'Route'): apply(obj)
    ensure_delivery(api, name, ns, project['id'], config, repo)
    # No build is seeded until the trusted stack and its credentials are present.
    oc('get', 'pipelines.tekton.dev', 'app-push', '-n', ns, '-o', 'json')
    ensure_project_scanner(name, ns, project['id'])
    route_host = oc('get', 'route', 'gitlab-webhook', '-n', ns, '-o', 'json')['spec']['host']
    hook_url = 'https://' + route_host
    hooks = api.request('GET', f"projects/{project['id']}/hooks")
    value = {'url': hook_url, 'push_events': True, 'push_events_branch_filter': 'main', 'enable_ssl_verification': True,
             'token': base64.b64decode(hook['data']['token']).decode()}
    match = next((h for h in hooks if h['url'] == hook_url), None)
    api.request('PUT' if match else 'POST', f"projects/{project['id']}/hooks" + ('/' + str(match['id']) if match else ''), value)
    try:
        oc('get', 'configmap', 'initial-build-receipt', '-n', ns, '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        run = pipeline_run(name, ns, project['id'], repo, row['initial_commit'])
        try: oc('create', '-f', '-', document=run)
        except subprocess.CalledProcessError as create_error:
            if '(AlreadyExists)' not in create_error.stderr: raise
        oc('create', '-f', '-', document=resource('ConfigMap', 'initial-build-receipt', ns, {'immutable': True, 'data': {'source_commit': row['initial_commit'], 'pipeline_run': run['metadata']['name']}}, 'v1'))
    if row['kind'] == 'migration':
        # A project-scoped API reader supplies only the immutable declaration.
        try:
            oc('get', 'secret', 'migration-source-' + name, '-n', 'app-platform-build', '-o', 'json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in error.stderr: raise
            token = api.request('POST', f"projects/{project['id']}/access_tokens", {'name': 'run-declaration-reader', 'scopes': ['read_api'], 'access_level': 20})
            ensure_secret('migration-source-' + name, 'app-platform-build', {'token': token['token']})
        # Only the platform coordinator may dispatch the privileged provisioner.


def provision_migration(name, row, project, config):
    """Dispatch an exact request after the project bootstrap succeeded."""
    provisioning = resource('PipelineRun', 'provision-' + name, 'app-platform-build', {'spec': {
            'pipelineRef': {'name': 'provision-migration-run'}, 'taskRunTemplate': {'serviceAccountName': 'migration-run-provisioner'},
            'params': [{'name': 'run-name', 'value': name}, {'name': 'scaffold-commit', 'value': row['initial_commit']},
                       {'name': 'request-repository-owner', 'value': config['GITLAB_WORKLOAD_GROUP']},
                       {'name': 'request-raw-base', 'value': config['GITLAB_BASE_URL'] + '/api/v4/projects'},
                       {'name': 'request-provider', 'value': 'gitlab'}, {'name': 'request-project-id', 'value': str(project['id'])}]}}, 'tekton.dev/v1')
    try:
        existing = oc('get', 'pipelineruns.tekton.dev', provisioning['metadata']['name'], '-n', 'app-platform-build', '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        try:
            oc('create', '-f', '-', document=provisioning)
            return
        except subprocess.CalledProcessError as create_error:
            if '(AlreadyExists)' not in create_error.stderr: raise
        existing = oc('get', 'pipelineruns.tekton.dev', provisioning['metadata']['name'], '-n', 'app-platform-build', '-o', 'json')
    spec = existing.get('spec', {})
    expected = provisioning['spec']
    if (spec.get('pipelineRef') != expected['pipelineRef']
            or spec.get('params') != expected['params']
            or spec.get('taskRunTemplate', {}).get('serviceAccountName') != 'migration-run-provisioner'
            or any(key in spec for key in ('pipelineSpec', 'taskRunSpecs', 'workspaces'))
            or spec.get('taskRunTemplate', {}).get('podTemplate')):
        raise ValueError('Existing migration provisioning request has a foreign identity or override')


def authorize_requester(api, row, project, config):
    ref = row.get('requester', '')
    identities = config.get('GITLAB_REQUESTER_IDS', {})
    names = config.get('GITLAB_REQUESTER_NAMES', {})
    if ref not in identities or not names.get(ref): raise ValueError('Requester is not an approved portal identity')
    person = api.request('GET', 'users/' + str(identities[ref]))
    member = api.request('GET', "projects/%s/members/all/%s" % (project['id'], identities[ref]))
    if person.get('state') != 'active' or person.get('username') != names[ref] or member.get('access_level', 0) < 30:
        raise ValueError('Requester is inactive or lacks this project membership')


def project_application(name, ns, row, config):
    return resource('Application', 'project-' + name, 'openshift-gitops', {'spec': {
        'project': 'platform-projects',
        'source': {'repoURL': config['PLATFORM_REPO_URL'], 'targetRevision': config['PLATFORM_REVISION'],
                   'path': 'gitops/stages/070-advanced-app-platform/070-pipelines/project-enrollment',
                   'kustomize': {'commonAnnotations': {'rhoai3.io/project-name': name, 'rhoai3.io/project-namespace': ns,
                                                       'rhoai3.io/enrollment': json.dumps(row, sort_keys=True)}}},
        'destination': {'server': 'https://kubernetes.default.svc', 'namespace': ns},
        # The child, not the root stage, owns these objects. Preserve only
        # controller-assigned CA data and the bound PVC's volume identity.
        'ignoreDifferences': [
            {'group':'','kind':'ConfigMap','name':'pipeline-registry-ca','namespace':ns,'jsonPointers':['/data']},
            {'group':'','kind':'PersistentVolumeClaim','name':'maven-cache','namespace':ns,'jsonPointers':['/spec/volumeName']}],
        'syncPolicy': {'automated': {'prune': True, 'selfHeal': True}, 'syncOptions': ['SkipDryRunOnMissingResource=true','RespectIgnoreDifferences=true']}}}, 'argoproj.io/v1alpha1')


def enroll(api, row, project, commit, config, import_receipt=None):
    name = validate_request(row, project, commit, int(config['GITLAB_WORKLOAD_GROUP_ID']), import_receipt)
    if import_receipt is None: authorize_requester(api, row, project, config)
    ns = row['namespace'] if import_receipt else name + '-dev'
    try:
        existing = oc('get', 'namespace', ns, '-o', 'json')
        if import_receipt is None and existing['metadata'].get('labels', {}).get('rhoai3.io/gitlab-project-id') != str(project['id']):
            raise ValueError('Namespace is not owned by this GitLab project')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        namespace = resource('Namespace', ns, '', {}, 'v1')
        namespace['metadata']['labels'] = {'rhoai3.redhat.com/pipeline-project':'true','rhoai3.io/gitlab-project-id':str(project['id'])}
        oc('create', '-f', '-', document=namespace)
    apply(project_application(name, ns, row, config))
    app = oc('get', 'application', 'project-' + name, '-n', 'openshift-gitops', '-o', 'json')
    status = app.get('status',{})
    if status.get('operationState', {}).get('phase') in ('Failed', 'Error'):
        raise ValueError('Platform-owned project bootstrap failed; inspect its native operation')
    if (status.get('health',{}).get('status') != 'Healthy'
            or status.get('sync',{}).get('status') != 'Synced'
            or status.get('sync',{}).get('revision') != config['PLATFORM_REVISION']
            or status.get('operationState',{}).get('phase') != 'Succeeded') :
        raise EnrollmentPending('Platform-owned project bootstrap is not yet complete')
    if row['kind'] == 'migration':
        provision_migration(name, row, project, config)
    mount_project_scanner(name, ns, row, project['id'])


def main():
    config = json.loads(oc('get','configmap','gitlab-platform-config','-n','app-platform-build','-o','json')['data']['platform.json'])
    api = GitLab(config['GITLAB_BASE_URL'], base64.b64decode(oc('get','secret','gitlab-enroller','-n','app-platform-build','-o','json')['data']['token']).decode())
    if os.environ.get('MODE') == 'bootstrap':
        row = json.loads(os.environ['ENROLLMENT'])
        if row.get('kind') == 'imported-application':
            seeds = oc('get','configmap','gitlab-import-seeds','-n','app-platform-build','-o','json')
            if not seeds.get('immutable'): raise ValueError('Import seed is not immutable')
            rows = json.loads(seeds['data']['seeds.json'])
            if len(rows) != 1: raise ValueError('Expected exactly one imported application seed')
            receipt = rows[0]
            if row != receipt: raise ValueError('Foreign imported enrollment')
        else:
            receipt = None
        project = api.request('GET','projects/' + str(row['project_id']))
        commit = api.request('GET', 'projects/%s/repository/commits/%s' % (project['id'], row['initial_commit']))
        if receipt is None: authorize_requester(api,row,project,config)
        bootstrap_project(api,row,project,commit,config,receipt)
        return
    seeds = oc('get','configmap','gitlab-import-seeds','-n','app-platform-build','-o','json')
    if not seeds.get('immutable'): raise ValueError('Imported-app seeds must be immutable')
    failures = 0
    for row in json.loads(seeds['data']['seeds.json']):
        try:
            project = api.request('GET','projects/' + str(row['project_id']))
            commit = api.request('GET','projects/%s/repository/commits/%s' % (project['id'],row['initial_commit']))
            enroll(api,row,project,commit,config,row)
        except EnrollmentPending:
            print('Imported project bootstrap pending: native operation incomplete')
        except (ValueError, KeyError, subprocess.CalledProcessError, urllib.error.URLError, TimeoutError):
            failures += 1
            print('REFUSE imported project bootstrap: validation or platform command failed')
    for page in range(1,11):
        issues = api.request('GET', "projects/%s/issues?state=opened&labels=platform-enrollment&per_page=100&page=%s" % (config['GITLAB_REGISTRATION_PROJECT_ID'],page))
        for issue in issues:
            if 'platform-enrollment-refused' in issue.get('labels', []):
                failures += 1
                print('REFUSE enrollment:', issue['iid'], 'requires correction of the recorded request')
                continue
            if issue['author']['id'] != int(config['GITLAB_PUBLISHER_USER_ID']):
                failures += 1
                print('REFUSE enrollment:', issue['iid'], 'author is not the trusted publisher'); continue
            try:
                row=json.loads(issue['description'])
                project=api.request('GET','projects/' + str(row['project_id']))
                commit=api.request('GET','projects/%s/repository/commits/%s' % (project['id'],row['initial_commit']))
                enroll(api,row,project,commit,config)
                api.request('PUT','projects/%s/issues/%s' % (config['GITLAB_REGISTRATION_PROJECT_ID'],issue['iid']),{'state_event':'close'})
                print('Enrollment complete:',project['path'])
            except (ValueError, KeyError, subprocess.CalledProcessError, urllib.error.URLError, TimeoutError) as error:
                state, reason = enrollment_failure(error, issue.get('created_at'))
                print('Enrollment ' + state + ':', issue['iid'], reason)
                if state == 'refused':
                    failures += 1
                    labels = sorted(set(issue.get('labels', []) + ['platform-enrollment-refused']))
                    api.request('PUT', 'projects/%s/issues/%s' % (config['GITLAB_REGISTRATION_PROJECT_ID'], issue['iid']), {'labels': ','.join(labels)})
        if len(issues)<100: break
    else: raise RuntimeError('Enrollment pagination bound reached')
    if failures:
        raise RuntimeError('Enrollment has terminal refusals; inspect the named requests')


if __name__ == '__main__': main()
