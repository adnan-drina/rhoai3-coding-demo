"""Platform enrollment from publisher-authored GitLab issues, never from push payloads."""
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
from urllib.parse import quote

SHA = re.compile(r'^[0-9a-f]{40}$')
NAME = re.compile(r'^[a-z][a-z0-9-]{2,40}$')


def oc(*args, document=None):
    result = subprocess.run(['oc', *args], input=None if document is None else json.dumps(document),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip().startswith('{') else result.stdout.strip()


def apply(document):
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
    return {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': ns}, **spec}


def trigger_resources(name, ns, project_id, repo, sha):
    listener = 'gitlab-listener'
    role = resource('Role', listener, ns, {'rules': [
        {'apiGroups': ['tekton.dev'], 'resources': ['pipelineruns'], 'verbs': ['create']},
        {'apiGroups': [''], 'resources': ['secrets'], 'resourceNames': ['gitlab-webhook'], 'verbs': ['get']},
        {'apiGroups': ['triggers.tekton.dev'], 'resources': ['eventlisteners', 'triggerbindings', 'triggertemplates', 'triggers', 'interceptors'], 'verbs': ['get', 'list', 'watch']} ]})
    subject = [{'kind': 'ServiceAccount', 'name': listener, 'namespace': ns}]
    binding = resource('RoleBinding', listener, ns, {'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': listener}, 'subjects': subject})
    cluster_binding = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding', 'metadata': {'name': 'gitlab-listener-' + name}, 'subjects': subject, 'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': 'tekton-triggers-eventlistener-clusterroles'}}
    template = resource('TriggerTemplate', 'gitlab-push', ns, {'spec': {'params': [{'name': 'revision'}], 'resourcetemplates': [pipeline_run(name, ns, project_id, repo, '$(tt.params.revision)')] }}, 'triggers.tekton.dev/v1beta1')
    event = resource('EventListener', 'gitlab', ns, {'spec': {'serviceAccountName': listener, 'triggers': [{
        'name': 'registered-main-push', 'interceptors': [
            {'ref': {'name': 'gitlab'}, 'params': [{'name': 'secretRef', 'value': {'secretName': 'gitlab-webhook', 'secretKey': 'token'}}, {'name': 'eventTypes', 'value': ['Push Hook']}]},
            {'ref': {'name': 'cel'}, 'params': [{'name': 'filter', 'value': f"body.project.id == {project_id} && body.project.git_http_url == '{repo}' && body.ref == 'refs/heads/main' && has(body.checkout_sha) && body.checkout_sha.matches('^[0-9a-f]{{40}}$') && body.checkout_sha != '{'0'*40}'"}]}],
        'bindings': [{'name': 'revision', 'value': '$(body.checkout_sha)'}], 'template': {'ref': 'gitlab-push'}}]}}, 'triggers.tekton.dev/v1beta1')
    route = resource('Route', 'gitlab-webhook', ns, {'spec': {'to': {'kind': 'Service', 'name': 'el-gitlab'}, 'port': {'targetPort': 8080}, 'tls': {'termination': 'edge', 'insecureEdgeTerminationPolicy': 'Redirect'}}}, 'route.openshift.io/v1')
    return [resource('ServiceAccount', listener, ns, {}, 'v1'), role, binding, cluster_binding, template, event, route]


def pipeline_run(name, ns, project_id, repo, revision):
    # Deterministic name makes duplicate delivery a harmless AlreadyExists, even before the hook returns.
    return resource('PipelineRun', f'gitlab-{project_id}-{revision}', ns, {'spec': {
        'pipelineRef': {'name': 'app-push'}, 'taskRunTemplate': {'serviceAccountName': 'app-builder'},
        'taskRunSpecs': [{'pipelineTaskName': 'build-and-push', 'serviceAccountName': 'image-builder'}],
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


def ensure_delivery(api, name, ns, source_project, config):
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
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        import datetime
        expiry = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
        token = api.request('POST', f"projects/{delivery['id']}/access_tokens", {'name': 'tekton-promoter', 'scopes': ['api'], 'access_level': 40, 'expires_at': expiry})
        ensure_secret('gitlab-delivery-writer', ns, {'token': token['token'], 'expires_at': expiry})
    clone = ensure_secret('gitlab-delivery-reader-' + name, 'openshift-gitops', {})
    if not clone.get('data'):
        token = api.request('POST', f"projects/{delivery['id']}/deploy_tokens", {'name': 'argocd-reader', 'scopes': ['read_repository']})
        apply(resource('Secret', 'gitlab-delivery-reader-' + name, 'openshift-gitops', {'type': 'Opaque', 'stringData': {'type': 'git', 'url': delivery['http_url_to_repo'], 'username': token['username'], 'password': token['token']}}, 'v1') | {'metadata': {'name': 'gitlab-delivery-reader-' + name, 'namespace': 'openshift-gitops', 'labels': {'argocd.argoproj.io/secret-type': 'repository'}}})
    reader = oc('get', 'secret', 'rhdh-argocd-reader', '-n', 'openshift-gitops', '-o', 'json')['data']['token']
    ensure_secret('argocd-delivery-reader', ns, {'token': base64.b64decode(reader).decode()})
    apply(resource('ConfigMap', 'project-delivery-config', ns, {'data': {'delivery.json': json.dumps({'repo_name': name, 'source_project_id': source_project, 'delivery_project_id': delivery['id'], 'gitlab_base_url': config['GITLAB_BASE_URL'], 'argocd_url': config['ARGOCD_URL']})}}, 'v1'))
    apply(resource('Application', 'runtime-' + name, 'openshift-gitops', {'spec': {'project': 'rhoai-demo', 'source': {'repoURL': delivery['http_url_to_repo'], 'targetRevision': 'main', 'path': '.'}, 'destination': {'server': 'https://kubernetes.default.svc', 'namespace': ns}, 'syncPolicy': {'automated': {'prune': True, 'selfHeal': True}, 'retry': {'limit': 10, 'backoff': {'duration': '5s', 'factor': 2, 'maxDuration': '3m'}}, 'syncOptions': ['ServerSideDiff=true', 'RespectIgnoreDifferences=true']}}}, 'argoproj.io/v1alpha1'))


def enroll(api, row, project, commit, config, import_receipt=None):
    name = validate_request(row, project, commit, int(config['GITLAB_WORKLOAD_GROUP_ID']), import_receipt)
    ns = row['namespace'] if import_receipt is not None else name + '-dev'
    repo = project['http_url_to_repo']
    namespace = resource('Namespace', ns, '', {}, 'v1')
    namespace['metadata']['labels'] = {'rhoai3.redhat.com/pipeline-project': 'true'}
    apply(namespace)
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
    for obj in trigger_resources(name, ns, project['id'], repo, row['initial_commit']): apply(obj)
    # Bootstrap only from platform manifests at a platform revision, not from the application repository.
    application = resource('Application', 'project-' + name, 'openshift-gitops', {'spec': {
        'project': 'rhoai-demo', 'source': {'repoURL': config['PLATFORM_REPO_URL'], 'targetRevision': config['PLATFORM_REVISION'], 'path': 'gitops/stages/070-advanced-app-platform/base/pipelines/project-pipeline', 'kustomize': {'namespace': ns, 'patches': [{'target': {'kind': 'ImageStream', 'name': 'application-image'}, 'patch': json.dumps([{'op': 'replace', 'path': '/metadata/name', 'value': name}])}, {'target': {'kind': 'RoleBinding', 'name': 'pipeline-image-builder'}, 'patch': json.dumps([{'op': 'add', 'path': '/subjects/0/namespace', 'value': ns}])}, {'target': {'kind': 'RoleBinding', 'name': 'pipeline-userns-builder'}, 'patch': json.dumps([{'op': 'add', 'path': '/subjects/0/namespace', 'value': ns}])}, {'target': {'kind': 'RoleBinding', 'name': 'pipeline-read-build-config'}, 'patch': json.dumps([{'op': 'add', 'path': '/subjects/0/namespace', 'value': ns}])}]}},
        'destination': {'server': 'https://kubernetes.default.svc', 'namespace': ns},
        'syncPolicy': {'automated': {'prune': True, 'selfHeal': True}, 'retry': {'limit': 10, 'backoff': {'duration': '5s', 'factor': 2, 'maxDuration': '3m'}}, 'syncOptions': ['SkipDryRunOnMissingResource=true', 'RespectIgnoreDifferences=true']}}}, 'argoproj.io/v1alpha1')
    if import_receipt is None:
        apply(application)
    # Coolstore's delivery tooling is already owned by Stage 070; never create
    # a second Argo owner for it. Only its runtime uses delivery Git.
    ensure_delivery(api, name, ns, project['id'], config)
    # No build is seeded until the trusted stack and its credentials are present.
    oc('get', 'pipeline', 'app-push', '-n', ns, '-o', 'json')
    scanner = oc('get', 'secret', 'sonarqube-credentials', '-n', 'app-platform-build', '-o', 'json')['data']
    if not scanner.get('host') or not scanner.get('token'):
        raise ValueError('Platform scanner credentials are incomplete')
    apply(resource('Secret', 'sonarqube-credentials', ns, {'type': 'Opaque',
          'data': {'host': scanner['host'], 'token': scanner['token']}}, 'v1'))
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
        # The existing platform Task owns run identity, databases, model pins and read-only control.
        provisioning = resource('PipelineRun', 'provision-' + name, 'app-platform-build', {'spec': {
            'pipelineRef': {'name': 'provision-migration-run'}, 'taskRunTemplate': {'serviceAccountName': 'migration-run-provisioner'},
            'params': [{'name': 'run-name', 'value': name}, {'name': 'scaffold-commit', 'value': row['initial_commit']},
                       {'name': 'request-repository-owner', 'value': config['GITLAB_WORKLOAD_GROUP']},
                       {'name': 'request-raw-base', 'value': config['GITLAB_BASE_URL'] + '/api/v4/projects'},
                       {'name': 'request-provider', 'value': 'gitlab'}, {'name': 'request-project-id', 'value': str(project['id'])}]}}, 'tekton.dev/v1')
        try: oc('create', '-f', '-', document=provisioning)
        except subprocess.CalledProcessError as error:
            if '(AlreadyExists)' not in error.stderr: raise


def main():
    config = json.loads(Path('/config/platform.json').read_text())
    api = GitLab(config['GITLAB_BASE_URL'], Path('/credentials/token').read_text().strip())
    seeds = oc('get', 'configmap', 'gitlab-import-seeds', '-n', 'app-platform-build', '-o', 'json')
    if not seeds.get('immutable'): raise ValueError('Imported-app seeds must be immutable')
    for row in json.loads(seeds['data']['seeds.json']):
        project = api.request('GET', 'projects/' + str(row['project_id']))
        commit = api.request('GET', f"projects/{project['id']}/repository/commits/{row['initial_commit']}")
        try:
            enroll(api, row, project, commit, config, import_receipt=row)
        except (subprocess.CalledProcessError, ValueError):
            print('Imported app enrollment waiting for platform delivery tooling')
    for page in range(1, 11):
        issues = api.request('GET', f"projects/{config['GITLAB_REGISTRATION_PROJECT_ID']}/issues?state=opened&labels=platform-enrollment&per_page=100&page={page}")
        for issue in issues:
            if issue['author']['id'] != int(config['GITLAB_PUBLISHER_USER_ID']):
                print('REFUSE enrollment: author is not the trusted publisher'); continue
            try:
                row = json.loads(issue['description'])
                project = api.request('GET', 'projects/' + str(row['project_id']))
                commit = api.request('GET', f"projects/{project['id']}/repository/commits/{row['initial_commit']}")
                enroll(api, row, project, commit, config)
                api.request('PUT', f"projects/{config['GITLAB_REGISTRATION_PROJECT_ID']}/issues/{issue['iid']}", {'state_event': 'close'})
                print('Enrollment complete:', project['path'])
            except (ValueError, KeyError, subprocess.CalledProcessError, urllib.error.HTTPError) as error:
                print('Enrollment pending:', issue['iid'], type(error).__name__)
        if len(issues) < 100: break
    else:
        raise RuntimeError('Enrollment pagination bound reached')


if __name__ == '__main__': main()
