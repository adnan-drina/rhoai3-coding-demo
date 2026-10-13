#!/usr/bin/env python3
"""Operator lifecycle for registered GitLab projects; preserves repository history."""
import argparse
import importlib.util
import io
import json
import os
import re
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]


def oc(*args):
    return json.loads(subprocess.check_output(['oc', *args], text=True))


def registration(name):
    ns = 'coolstore-dev' if name == 'coolstore-inventory-service' else name + '-dev'
    row = json.loads(oc('get', 'configmap', 'project-registration', '-n', ns, '-o', 'json')['data']['registration.json'])
    return ns, row


def check_registration(name, row, project):
    if not re.fullmatch('[a-z][a-z0-9-]{2,40}', name): raise ValueError('Invalid project name')
    if row['project_id'] != project['id'] or row['repo_url'] != project['http_url_to_repo']:
        raise ValueError('GitLab project differs from its immutable registration')
    if project['path'] != name or not re.fullmatch('[0-9a-f]{40}', row['initial_commit']):
        raise ValueError('Unbound project lifecycle request')


def check_action(action, name, row):
    if action == 'reset-coolstore':
        if name != 'coolstore-inventory-service' or row['kind'] != 'imported-application':
            raise ValueError('Reset is limited to the ordinary Coolstore demo, never a migration run')
    elif row['kind'] not in ('application', 'migration'):
        raise ValueError('Stage-owned imported applications cannot be retired by the project helper')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['reset-coolstore', 'retire'])
    parser.add_argument('name')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    if not args.yes: raise SystemExit('Pass --yes after reviewing the registered project and retained data.')
    # Public entry points source lib.sh and call both safety guards first.
    expected = os.environ.get('RHOAI_EXPECTED_API_SERVER', '')
    server = subprocess.check_output(['oc', 'whoami', '--show-server'], text=True).strip()
    if not expected or expected not in server: raise RuntimeError('Cluster guard does not match')
    config = json.loads(oc('get', 'configmap', 'gitlab-platform-config', '-n', 'app-platform-build', '-o', 'json')['data']['platform.json'])
    ns, row = registration(args.name)
    token_file = os.environ.get('GITLAB_OPERATOR_TOKEN_FILE')
    if not token_file: raise RuntimeError('GITLAB_OPERATOR_TOKEN_FILE must name your scoped operator token file')
    token = Path(token_file).read_text().strip()

    def api(method, path, data=None, raw=False):
        req = urllib.request.Request(config['GITLAB_BASE_URL'] + '/api/v4/' + path,
            None if data is None else json.dumps(data).encode(),
            {'PRIVATE-TOKEN': token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read(); return body if raw else json.loads(body) if body else None

    project = api('GET', 'projects/' + str(row['project_id']))
    check_registration(args.name, row, project)
    if project['path_with_namespace'] != config['GITLAB_WORKLOAD_GROUP'] + '/' + args.name:
        raise RuntimeError('Lifecycle target is outside the registered workload group')
    check_action(args.action, args.name, row)
    # Stop matching workspaces; retain their PVCs and local changes. Never wipe
    # a shared volume or change an unrelated/historical workspace.
    for namespace in ('wksp-ai-developer', 'wksp-ai-admin'):
        for dw in oc('get', 'devworkspaces', '-n', namespace, '-o', 'json')['items']:
            origins = [p.get('git', {}).get('remotes', {}).get('origin') for p in dw['spec']['template'].get('projects', [])]
            if row['repo_url'] in origins:
                subprocess.run(['oc', 'patch', 'devworkspace', dw['metadata']['name'], '-n', namespace,
                                '--type=merge', '-p', '{"spec":{"started":false}}'], check=True, stdout=subprocess.DEVNULL)
    pid = project['id']
    if args.action == 'reset-coolstore':
        if project.get('archived'): raise RuntimeError('Archived project cannot be reset')
        archive = api('GET', f"projects/{pid}/repository/archive.tar.gz?sha={row['initial_commit']}", raw=True)
        files = {}
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.isfile(): files[member.name.partition('/')[2]] = (tar.extractfile(member).read(), bool(member.mode & 0o111))
        current = {}
        for page in range(1, 31):
            rows = api('GET', f'projects/{pid}/repository/tree?ref=main&recursive=true&per_page=100&page={page}')
            current.update({r['path']: r for r in rows if r['type'] == 'blob'})
            if len(rows) < 100: break
        else: raise RuntimeError('Reset exceeds bounded inventory')
        spec = importlib.util.spec_from_file_location('golden', ROOT / 'gitops/stages/070-advanced-app-platform/base/gitlab/bootstrap-scm.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        actions = module.golden_actions(files, current)
        if actions:
            result = api('POST', f'projects/{pid}/repository/commits', {'branch': 'main',
                         'commit_message': 'chore: restore registered Coolstore baseline', 'actions': actions})
            print('Baseline restored by normal commit:', result['id'])
        else: print('Repository already matches its registered baseline')
        print('Workspace data retained. Review local changes before reopening/pulling main.')
        return
    # Archiving is the persistent retirement guard: the reconciler cannot
    # recreate resources for this project, even after its namespace is gone.
    api('POST', f'projects/{pid}/archive')
    if row['kind'] == 'migration':
        run = {'apiVersion': 'tekton.dev/v1', 'kind': 'PipelineRun',
               'metadata': {'generateName': 'retire-' + args.name + '-', 'namespace': 'app-platform-build'},
               'spec': {'taskRunTemplate': {'serviceAccountName': 'migration-run-provisioner'},
                        'pipelineRef': {'name': 'provision-migration-run'},
                        'params': [{'name': 'run-name', 'value': args.name}, {'name': 'scaffold-commit', 'value': row['initial_commit']}, {'name': 'mode', 'value': 'retire'}, {'name': 'request-project-id', 'value': str(pid)}]}}
        result = subprocess.run(['oc', 'create', '-f', '-', '-o', 'json'], input=json.dumps(run), text=True, capture_output=True, check=True)
        run_name = json.loads(result.stdout)['metadata']['name']
        subprocess.run(['oc', 'wait', 'pipelinerun', run_name, '-n', 'app-platform-build',
                        '--for=condition=Succeeded', '--timeout=600s'], check=True)
    for app in ('project-' + args.name, 'runtime-' + args.name):
        subprocess.run(['oc', 'delete', 'application', app, '-n', 'openshift-gitops', '--ignore-not-found'], check=True)
    subprocess.run(['oc', 'delete', 'namespace', ns, '--ignore-not-found'], check=True)
    print('Project retired. GitLab repository archived; workspace PVCs and delivery history retained.')


if __name__ == '__main__': main()
