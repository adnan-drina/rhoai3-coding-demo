"""Configure GitLab service identities and integrations using an ephemeral bootstrap PAT."""
import datetime
import base64
import hashlib
import io
import tarfile
import json
import secrets
import subprocess
import os
import re
import tempfile
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode


def sync_platform_revision(source_url, mirror_url, revision, token):
    """Retain reviewed Git history using a normal fast-forward, never force push."""
    if source_url != 'https://github.com/adnan-drina/rhoai3-coding-demo.git':
        raise ValueError('Platform bootstrap source is not the declared upstream repository')
    if not re.fullmatch(r'https://gitlab\.[a-z0-9.-]+/rhoai-platform/rhoai3-coding-demo\.git', mirror_url):
        raise ValueError('Platform mirror is outside its declared GitLab path')
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Platform source revision must be immutable')
    with tempfile.TemporaryDirectory(prefix='platform-mirror-') as work:
        auth = Path(work) / 'credentials'
        auth.write_text('https://oauth2:' + quote(token, safe='') + '@' + mirror_url.split('/')[2] + '\n')
        auth.chmod(0o600)
        env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'HOME': work}
        git = ['git', '-c', 'credential.helper=store --file=' + str(auth), '--git-dir=' + work + '/repo']
        def run(*args):
            return subprocess.run(git + list(args), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True, timeout=300)
        run('init', '--bare')
        run('remote', 'add', 'origin', mirror_url)
        run('fetch', '--no-tags', 'origin', 'main:refs/remotes/origin/main')
        run('fetch', '--no-tags', source_url, revision)
        run('merge-base', '--is-ancestor', 'refs/remotes/origin/main', revision)
        run('push', '--atomic', 'origin', revision + ':refs/heads/main')


def golden_files(archive, directory):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        for member in tar.getmembers():
            marker = '/' + directory + '/'
            if marker not in member.name: continue
            path = member.name.split(marker, 1)[1]
            if member.isdir(): continue
            if not member.isfile(): raise ValueError('Golden archive contains a link or special file')
            if not path or path in files: raise ValueError('Golden archive contains duplicate or empty paths')
            if '__pycache__' in path.split('/') or path.startswith('.hermes/_park/'): continue
            files[path] = (tar.extractfile(member).read(), bool(member.mode & 0o111))
    if not {'devfile.yaml', 'AGENTS.md'}.issubset(files):
        raise RuntimeError('Platform revision has no complete golden')
    # Validate the complete path set before any GitLab commit is sent.
    golden_actions(files, {})
    return files


def imported_runtime_commit(existing, contents):
    """An import retry may reuse only the reviewed file's actual commit."""
    if existing.get('encoding') != 'base64':
        raise RuntimeError('Imported runtime has an unsupported encoding')
    if base64.b64decode(existing['content'], validate=True).decode() != contents:
        raise RuntimeError('Imported runtime differs from the platform-reviewed artifact')
    commit = existing.get('last_commit_id', '')
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise RuntimeError('Imported runtime has no immutable commit identity')
    return commit


def golden_actions(files, current):
    """One ordinary commit replaces the golden tree, preserving its history."""
    actions = []
    for path, (content, executable) in sorted(files.items()):
        if path.startswith('/') or '..' in path.split('/') or '.git' in path.split('/'):
            raise ValueError('Unsafe golden file path')
        if '__pycache__' in path.split('/') or path.startswith('.hermes/_park/'):
            raise ValueError('Authoring debris in the golden tree')
        if path.endswith('run-chaos-matrix.py'):
            raise ValueError('Forbidden execution fixture in golden')
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        old = current.get(path)
        if old and old['id'] == blob and (old.get('mode') == '100755') == executable:
            continue
        actions.append({'action': 'update' if old else 'create', 'file_path': path,
                        'content': base64.b64encode(content).decode(), 'encoding': 'base64',
                        'execute_filemode': executable})
    actions.extend({'action': 'delete', 'file_path': path} for path in sorted(set(current) - set(files)))
    if len(json.dumps(actions).encode()) > 10_000_000:
        raise RuntimeError('Golden publication exceeds one bounded atomic commit')
    return actions


def realm_personas():
    """Only the two already-brokered OpenShift identities receive membership."""
    host = oc('get', 'route', 'keycloak', '-n', 'keycloak', '-o', 'json')['spec']['host']
    admin = oc('get', 'secret', 'stage070-scm-provisioner', '-n', 'gitlab-system', '-o', 'json')['data']
    credentials = {key: base64.b64decode(admin[key]).decode() for key in ('client_id', 'client_secret')}
    base = 'https://' + host
    request = urllib.request.Request(base + '/realms/platform/protocol/openid-connect/token',
        urlencode({'grant_type': 'client_credentials', **credentials}).encode(),
        {'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response: token = json.load(response)['access_token']
    rows = []
    for username in ('ai-developer', 'ai-admin'):
        request = urllib.request.Request(base + '/admin/realms/platform/users?username=' + username + '&exact=true',
                                         headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(request, timeout=30) as response: matches = json.load(response)
        if len(matches) != 1 or not matches[0].get('emailVerified'):
            raise RuntimeError('Verified platform persona missing: ' + username)
        rows.append(matches[0])
    return rows


def check_oidc_identity(user, subject):
    identities = [row for row in user.get('identities', []) if row.get('provider') == 'openid_connect']
    if any(row.get('extern_uid') != subject for row in identities):
        raise RuntimeError('GitLab user is bound to another OIDC subject')
    return bool(identities)


def oc(*args, data=None):
    result = subprocess.run(['oc', *args], input=None if data is None else json.dumps(data), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    return json.loads(result.stdout) if result.stdout.lstrip().startswith('{') else None


def apply(kind, name, ns, data, labels=None, annotations=None):
    return oc('apply', '-f', '-', data={'apiVersion': 'v1', 'kind': kind,
        'metadata': {'name': name, 'namespace': ns, 'labels': labels or {}, 'annotations': annotations or {}},
        'stringData' if kind == 'Secret' else 'data': data})


def main():
    domain = oc('get', 'ingress.config.openshift.io', 'cluster', '-o', 'json')['spec']['domain']
    host = oc('get', 'route', 'gitlab', '-n', 'gitlab-system', '-o', 'json')['spec']['host']
    if not host.endswith('.' + domain): raise RuntimeError('GitLab Route is outside the ingress domain')
    base = 'https://' + host
    for _ in range(90):
        try:
            with urllib.request.urlopen(base + '/-/readiness', timeout=10) as response:
                if response.status == 200: break
        except (urllib.error.URLError, TimeoutError): pass
        time.sleep(10)
    else: raise RuntimeError('GitLab readiness deadline exceeded')
    pods = oc('get', 'pods', '-n', 'gitlab-system', '-l', 'app=toolbox,release=gitlab', '-o', 'json')['items']
    pods = [p for p in pods if any(c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', []))]
    if len(pods) != 1: raise RuntimeError('Expected exactly one Ready GitLab toolbox')
    # Ruby runs only in the platform-owned toolbox, never in an application workspace.
    ruby = "u=User.find_by_username!('root'); t=u.personal_access_tokens.create!(name:'stage070-bootstrap',scopes:['api'],expires_at:1.day.from_now); puts t.token"
    output = subprocess.check_output(['oc', 'exec', '-n', 'gitlab-system', pods[0]['metadata']['name'], '-c', 'toolbox', '--', 'gitlab-rails', 'runner', ruby], universal_newlines=True)
    token = output.strip().splitlines()[-1]
    if not token.startswith('glpat-'): raise RuntimeError('GitLab bootstrap PAT was not produced')

    def api(method, path, payload=None, raw=False):
        req = urllib.request.Request(base + '/api/v4/' + path, None if payload is None else json.dumps(payload).encode(), {'PRIVATE-TOKEN': token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return body if raw else json.loads(body) if body else None

    def find(path, query):
        rows = api('GET', path + '?' + query)
        if len(rows) > 100: raise RuntimeError('Bootstrap lookup exceeded its bound')
        return rows

    def group(path):
        rows = find('groups', 'search=' + quote(path))
        return next((r for r in rows if r['full_path'] == path), None) or api('POST', 'groups', {'name': path, 'path': path, 'visibility': 'private'})

    try:
        platform, workloads, delivery = [group(p) for p in ('rhoai-platform', 'rhoai-workloads', 'rhoai-delivery')]
        api('PUT', 'application/settings', {'signup_enabled': False})
        api('PUT', f"groups/{workloads['id']}", {'project_creation_level': 'developer',
            'default_branch': 'main', 'default_branch_protection_defaults': {
                'allowed_to_push': [{'access_level': 30}], 'allowed_to_merge': [{'access_level': 40}],
                'allow_force_push': False, 'developer_can_initial_push': True}})

        def user(username):
            rows = find('users', 'username=' + username)
            return next((r for r in rows if r['username'] == username), None) or api('POST', 'users', {'username': username, 'name': username, 'email': username + '@example.invalid', 'password': secrets.token_urlsafe(40), 'skip_confirmation': True})

        def membership(group_id, user_id, level):
            try: api('POST', f'groups/{group_id}/members', {'user_id': user_id, 'access_level': level})
            except urllib.error.HTTPError as error:
                if error.code != 409: raise
                current = api('GET', f'groups/{group_id}/members/{user_id}')
                if current['access_level'] != level: api('PUT', f'groups/{group_id}/members/{user_id}', {'access_level': level})

        requesters = {}
        for persona in realm_personas():
            username = persona['username']
            rows = find('users', 'username=' + username)
            account = next((r for r in rows if r['username'] == username), None)
            if account is None:
                account = api('POST', 'users', {'username': username, 'name': username,
                    'email': persona['email'], 'force_random_password': True, 'skip_confirmation': True,
                    'provider': 'openid_connect', 'extern_uid': persona['id']})
            elif not check_oidc_identity(account, persona['id']):
                if account['email'] != persona['email']:
                    raise RuntimeError('Refuse to link a foreign GitLab account: ' + username)
                api('PUT', 'users/' + str(account['id']), {'provider': 'openid_connect', 'extern_uid': persona['id']})
            requesters['user:default/' + username] = account['id']
            membership(workloads['id'], account['id'], 40 if username == 'ai-admin' else 30)
            membership(platform['id'], account['id'], 20)
            membership(delivery['id'], account['id'], 20)

        publisher, enroller, reader = [user(u) for u in ('rhdh-publisher', 'platform-enroller', 'platform-catalog-reader')]
        for identity, groups in ((publisher, [(workloads, 40), (platform, 20)]), (enroller, [(workloads, 50), (delivery, 50), (platform, 20)]), (reader, [(platform, 20)])):
            for g, level in groups: membership(g['id'], identity['id'], level)

        def credential(username, scopes, secret_name, ns):
            try:
                existing = oc('get', 'secret', secret_name, '-n', ns, '-o', 'json')
                # Missing expiry or an expired secret is a refusal, never a silent remint.
                expiry = datetime.datetime.strptime(existing['metadata']['annotations']['rhoai3.io/expires-at'], '%Y-%m-%d').date()
                if expiry <= datetime.date.today() + datetime.timedelta(days=7): raise RuntimeError('GitLab service token needs a reviewed rotation: ' + secret_name)
                return existing
            except subprocess.CalledProcessError as error:
                if '(NotFound)' not in error.stderr: raise
            u = user(username); expiry = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
            row = api('POST', f"users/{u['id']}/personal_access_tokens", {'name': 'stage070-' + username, 'scopes': scopes, 'expires_at': expiry})
            return apply('Secret', secret_name, ns, {'token': row['token']}, annotations={'rhoai3.io/expires-at': expiry})

        publish_secret = credential('rhdh-publisher', ['api', 'read_repository'], 'gitlab-publisher', 'rhdh')
        credential('platform-enroller', ['api', 'read_repository'], 'gitlab-enroller', 'app-platform-build')
        read_secret = credential('platform-catalog-reader', ['read_api', 'read_repository'], 'gitlab-catalog-reader', 'rhdh')

        def project(group, name, origin=None):
            try: p = api('GET', 'projects/' + quote(group['path'] + '/' + name, safe=''))
            except urllib.error.HTTPError as error:
                if error.code != 404: raise
                payload = {'name': name, 'path': name, 'namespace_id': group['id'], 'visibility': 'private'}
                if origin: payload['import_url'] = origin
                else: payload['initialize_with_readme'] = True
                p = api('POST', 'projects', payload)
            if origin:
                for _ in range(120):
                    p = api('GET', 'projects/' + str(p['id']))
                    status = p.get('import_status')
                    if status in ('finished', 'none'): break
                    if status == 'failed': raise RuntimeError('GitLab import failed: ' + name)
                    time.sleep(5)
                else: raise RuntimeError('GitLab import deadline exceeded: ' + name)
            return p

        registration = project(platform, 'platform-enrollment')
        # Publisher may create enrollment issues, but cannot modify platform code.
        try: api('POST', f"projects/{registration['id']}/members", {'user_id': publisher['id'], 'access_level': 30})
        except urllib.error.HTTPError as error:
            if error.code != 409: raise
        imports = {}
        for name in ('rhoai3-coding-demo', 'agentic-quarkus-scaffold', 'quarkus-migration-scaffold-v2'):
            imports[name] = project(platform, name, 'https://github.com/adnan-drina/' + name + '.git')
        for name in ('coolstore-inventory-service', 'spring-petclinic-rest-legacy', 'coolstore-cart-legacy'):
            imports[name] = project(workloads, name, 'https://github.com/adnan-drina/' + name + '.git')
        # Preserve the first imported-app seed across syncs. Imported history
        # has parents, unlike a new migration declaration; only this immutable,
        # platform-written packet authorizes that separate enrollment path.
        try:
            oc('get', 'configmap', 'gitlab-import-seeds', '-n', 'app-platform-build', '-o', 'json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in error.stderr: raise
            app = imports['coolstore-inventory-service']
            contents = Path('/bootstrap/coolstore-runtime.json').read_text()
            file_path = 'k8s-run/platform-app.yaml'
            try:
                existing = api('GET', f"projects/{app['id']}/repository/files/{quote(file_path, safe='')}?ref=main")
            except urllib.error.HTTPError as error:
                if error.code != 404: raise
                head = api('POST', f"projects/{app['id']}/repository/commits", {
                    'branch': 'main', 'commit_message': 'chore: declare platform-reviewed runtime assets',
                    'actions': [{'action': 'create', 'file_path': file_path, 'content': contents}]})['id']
            else:
                head = imported_runtime_commit(existing, contents)
            seed = {'project_id': app['id'], 'initial_commit': head,
                    'kind': 'imported-application', 'namespace': 'coolstore-dev'}
            oc('create', '-f', '-', data={'apiVersion': 'v1', 'kind': 'ConfigMap',
                'metadata': {'name': 'gitlab-import-seeds', 'namespace': 'app-platform-build'},
                'immutable': True, 'data': {'seeds.json': json.dumps([seed])}})
        publish_token = base64.b64decode(publish_secret['data']['token']).decode()
        apply('Secret', 'rhdh-gitlab', 'rhdh', {'GITLAB_HOST': host, 'GITLAB_BASE_URL': base, 'GITLAB_PUBLISHER_TOKEN': publish_token})
        argo_host = oc('get', 'route', 'openshift-gitops-server', '-n', 'openshift-gitops', '-o', 'json')['spec']['host']
        try:
            oc('get', 'secret', 'rhdh-argocd-reader', '-n', 'openshift-gitops', '-o', 'json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in error.stderr: raise
            admin = oc('get', 'secret', 'openshift-gitops-cluster', '-n', 'openshift-gitops', '-o', 'json')
            password = base64.b64decode(admin['data']['admin.password']).decode()
            argo_base = 'https://' + argo_host
            def argo(method, path, payload, bearer=None):
                headers = {'Content-Type': 'application/json'}
                if bearer: headers['Authorization'] = 'Bearer ' + bearer
                request = urllib.request.Request(argo_base + '/api/v1/' + path, json.dumps(payload).encode(), headers, method=method)
                with urllib.request.urlopen(request, timeout=30) as response: return json.load(response)
            session = argo('POST', 'session', {'username': 'admin', 'password': password})['token']
            read_token = argo('POST', 'account/rhdh/token', {'expiresIn': 7776000}, session)['token']
            apply('Secret', 'rhdh-argocd-reader', 'openshift-gitops', {'token': read_token})
        synced = oc('get', 'application', '070-advanced-app-platform', '-n', 'openshift-gitops', '-o', 'json')
        platform_sha = (synced.get('status', {}).get('operationState', {}).get('syncResult', {}).get('revision')
                        or synced.get('status', {}).get('sync', {}).get('revision'))
        if not platform_sha or not re.fullmatch('[0-9a-f]{40}', platform_sha): raise RuntimeError('Stage 070 has no immutable source revision')
        mirror = imports['rhoai3-coding-demo']
        try:
            api('GET', f"projects/{mirror['id']}/repository/commits/{platform_sha}")
        except urllib.error.HTTPError as error:
            if error.code != 404: raise
            sync_platform_revision(synced['spec']['source']['repoURL'], mirror['http_url_to_repo'], platform_sha, token)
            measured = api('GET', f"projects/{mirror['id']}/repository/commits/{platform_sha}")
            if measured['id'] != platform_sha: raise RuntimeError('Platform mirror did not retain the reviewed commit')
        # Publish owned goldens from the reviewed platform revision, rather
        # than retaining the older GitHub golden after an upgrade. The mirror
        # must contain that revision; a missing source refuses the whole sync.
        for name, directory in (
            ('agentic-quarkus-scaffold', 'stages/120-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold'),
            ('quarkus-migration-scaffold-v2', 'stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold')):
            archive = api('GET', f"projects/{imports['rhoai3-coding-demo']['id']}/repository/archive.tar.gz?sha={platform_sha}&path={quote(directory, safe='')}", raw=True)
            files = golden_files(archive, directory)
            current = {}
            for page in range(1, 31):
                rows = api('GET', f"projects/{imports[name]['id']}/repository/tree?ref=main&recursive=true&per_page=100&page={page}")
                current.update({row['path']: row for row in rows if row['type'] == 'blob'})
                if len(rows) < 100: break
            else: raise RuntimeError('Golden tree exceeds publication bound')
            actions = golden_actions(files, current)
            if actions:
                api('POST', f"projects/{imports[name]['id']}/repository/commits", {
                    'branch': 'main', 'commit_message': 'chore: publish reviewed platform golden ' + platform_sha,
                    'actions': actions})
        platform_repo = imports['rhoai3-coding-demo']['http_url_to_repo']
        try:
            oc('get', 'secret', 'gitlab-platform-reader', '-n', 'openshift-gitops', '-o', 'json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in error.stderr: raise
            read = api('POST', f"projects/{imports['rhoai3-coding-demo']['id']}/deploy_tokens", {
                'name': 'argocd-platform-reader', 'scopes': ['read_repository']})
            apply('Secret', 'gitlab-platform-reader', 'openshift-gitops', {
                'type': 'git', 'url': platform_repo, 'username': read['username'], 'password': read['token']},
                {'argocd.argoproj.io/secret-type': 'repository'})
        config = {'GITLAB_HOST': host, 'GITLAB_BASE_URL': base, 'GITLAB_WORKLOAD_GROUP': workloads['path'], 'GITLAB_WORKLOAD_GROUP_ID': str(workloads['id']), 'GITLAB_DELIVERY_GROUP': delivery['path'], 'GITLAB_DELIVERY_GROUP_ID': str(delivery['id']), 'GITLAB_PUBLISHER_USER_ID': str(publisher['id']), 'GITLAB_REGISTRATION_PROJECT_ID': str(registration['id']), 'PLATFORM_REPO_URL': platform_repo, 'PLATFORM_REVISION': platform_sha, 'ARGOCD_URL': 'https://' + argo_host}
        config['GITLAB_REQUESTER_IDS'] = requesters
        apply('ConfigMap', 'stage070-project-release', 'openshift-gitops', {'repo_url': platform_repo, 'revision': platform_sha, 'delivery_base_url': base + '/' + delivery['path'] + '/'})
        config['PLATFORM_CATALOG_REPO'] = imports['rhoai3-coding-demo']['http_url_to_repo']
        mta_host = oc('get', 'route', 'mta', '-n', 'openshift-mta', '-o', 'json')['spec']['host']
        if not mta_host.endswith('.' + domain): raise RuntimeError('MTA Route is outside the ingress domain')
        config['MTA_HUB_URL'] = 'https://' + mta_host
        for namespace in ('wksp-ai-developer', 'wksp-ai-admin'):
            workspace = oc('get', 'devworkspace', 'agentic-coolstore', '-n', namespace, '-o', 'json')
            if workspace['spec'].get('started'):
                raise RuntimeError('Stop the standing workspace before changing its source: ' + namespace)
            url = imports['coolstore-inventory-service']['http_url_to_repo']
            patch = [{'op': 'replace', 'path': '/spec/template/projects/0/git/remotes/origin', 'value': url}]
            oc('patch', 'devworkspace', 'agentic-coolstore', '-n', namespace, '--type=json', '-p', json.dumps(patch))
        for name in ('agentic-quarkus-scaffold', 'quarkus-migration-scaffold-v2'):
            p = imports[name]; head = api('GET', f"projects/{p['id']}/repository/branches/main")['commit']['id']
            config[name] = base + '/' + p['path_with_namespace'] + '/-/tree/' + head
        apply('ConfigMap', 'gitlab-platform-config', 'app-platform-build', {'platform.json': json.dumps(config)})
        apply('ConfigMap', 'gitlab-platform-config', 'rhdh', {'platform.json': json.dumps(config)})
        # Native Dev Spaces GitLab OAuth application and native SCM Secret metadata.
        che_host = oc('get', 'route', 'devspaces', '-n', 'openshift-devspaces', '-o', 'json')['spec']['host']
        try:
            oc('get', 'secret', 'gitlab-oauth-config', '-n', 'openshift-devspaces', '-o', 'json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in error.stderr: raise
            apps = api('GET', 'applications')
            if any(a['name'] == 'Dev Spaces' for a in apps):
                raise RuntimeError('Existing Dev Spaces OAuth application lost its Secret; reviewed rotation required')
            oauth = api('POST', 'applications', {'name': 'Dev Spaces', 'redirect_uri': 'https://' + che_host + '/api/oauth/callback', 'scopes': 'api write_repository openid', 'confidential': True})
            apply('Secret', 'gitlab-oauth-config', 'openshift-devspaces', {'id': oauth['application_id'], 'secret': oauth['secret']}, {'app.kubernetes.io/part-of': 'che.eclipse.org', 'app.kubernetes.io/component': 'oauth-scm-configuration'}, {'che.eclipse.org/oauth-scm-server': 'gitlab', 'che.eclipse.org/scm-server-endpoint': base})
        oc('patch', 'checluster', 'devspaces', '-n', 'openshift-devspaces', '--type=merge', '-p', json.dumps({'spec': {'gitServices': {'gitlab': [{'secretName': 'gitlab-oauth-config', 'endpoint': base}]}, 'devEnvironments': {'allowedSources': {'urls': [base + '/' + workloads['path'] + '/*', base + '/' + platform['path'] + '/*']}}}}))
    finally:
        # Revoke even if an import, enrollment or OAuth setup fails. A retry
        # uses a new short-lived bootstrap credential, never an old root token.
        api('DELETE', 'personal_access_tokens/self')
    print('GitLab identities, repository imports and Dev Spaces OAuth configured')


if __name__ == '__main__': main()
