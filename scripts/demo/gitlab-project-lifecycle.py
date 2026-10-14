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
    result = subprocess.run(['oc', *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def registration(name):
    ns = 'coolstore-dev' if name == 'coolstore-inventory-service' else name + '-dev'
    try:
        row = json.loads(oc('get', 'configmap', 'project-registration', '-n', ns, '-o', 'json')['data']['registration.json'])
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in (error.stderr or ''): raise
        saved = oc('get', 'configmap', 'retired-project-' + name, '-n', 'app-platform-build', '-o', 'json')
        packet = json.loads(saved['data']['retirement.json'])
        if packet['name'] != name or packet['namespace'] != ns: raise ValueError('Foreign retirement record')
        row = packet['registration']
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
    if args.action == 'retire':
        packet = {'name':args.name, 'namespace':ns, 'registration':row}
        tombstone = {'apiVersion':'v1','kind':'ConfigMap','metadata':{
            'name':'retired-project-'+args.name,'namespace':'app-platform-build'},
            'immutable':True,'data':{'retirement.json':json.dumps(packet,sort_keys=True)}}
        try:
            old = oc('get','configmap',tombstone['metadata']['name'],'-n','app-platform-build','-o','json')
            if old.get('data') != tombstone['data']:raise ValueError('Retirement record identity changed')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in (error.stderr or ''):raise
            subprocess.run(['oc','create','-f','-'],input=json.dumps(tombstone),text=True,check=True,stdout=subprocess.DEVNULL)
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
        spec = importlib.util.spec_from_file_location('golden', ROOT / 'gitops/stages/070-advanced-app-platform/gitlab/bootstrap-scm.py')
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
    if not project.get('archived'):
        api('POST', f'projects/{pid}/archive')
    if row['kind'] == 'migration':
        run = {'apiVersion': 'tekton.dev/v1', 'kind': 'PipelineRun',
               'metadata': {'name': 'retire-' + args.name, 'namespace': 'app-platform-build'},
               'spec': {'taskRunTemplate': {'serviceAccountName': 'migration-run-provisioner'},
                        'pipelineRef': {'name': 'provision-migration-run'},
                        'params': [{'name': 'run-name', 'value': args.name}, {'name': 'scaffold-commit', 'value': row['initial_commit']}, {'name': 'mode', 'value': 'retire'}, {'name': 'request-project-id', 'value': str(pid)}]}}
        try:
            recorded = oc('get','pipelinerun',run['metadata']['name'],'-n','app-platform-build','-o','json')
        except subprocess.CalledProcessError as error:
            if '(NotFound)' not in (error.stderr or ''):raise
            result = subprocess.run(['oc','create','-f','-','-o','json'],input=json.dumps(run),text=True,capture_output=True,check=True)
            recorded = json.loads(result.stdout)
        expected = {p['name']:p['value'] for p in run['spec']['params']}
        actual = {p['name']:p['value'] for p in recorded['spec']['params']}
        if actual != expected or recorded['spec']['pipelineRef'] != run['spec']['pipelineRef']:
            raise ValueError('Existing retirement PipelineRun has another identity')
        conditions = recorded.get('status',{}).get('conditions',[])
        if any(c.get('type')=='Succeeded' and c.get('status')=='False' for c in conditions):
            raise RuntimeError('Retirement pipeline failed; preserve it, repair its cause and review a native retry. Namespace retained.')
        subprocess.run(['oc','wait','pipelinerun',run['metadata']['name'],'-n','app-platform-build',
                        '--for=condition=Succeeded','--timeout=600s'],check=True)
    for app in ('project-' + args.name, 'runtime-' + args.name):
        subprocess.run(['oc', 'delete', 'application', app, '-n', 'openshift-gitops', '--ignore-not-found'], check=True)
    # Child Applications have no destructive finalizers. Remove only their
    # registered cross-namespace grants; repository and delivery history remain.
    for namespace, kind, names in (
            ('app-platform-build','rolebinding',[args.name+'.inputs',args.name+'.runs']),
            ('app-platform-build','role',[args.name+'.runs']),
            ('openshift-gitops','rolebinding',[args.name+'.delivery',args.name+'.readback']),
            ('openshift-gitops','role',[args.name+'.delivery',args.name+'.readback']),
            ('openshift-gitops','secret',['gitlab-delivery-reader-'+args.name])):
        subprocess.run(['oc','delete',kind,*names,'-n',namespace,'--ignore-not-found'],check=True)
    subprocess.run(['oc','delete','clusterrolebinding',args.name+'.listener','--ignore-not-found'],check=True)
    subprocess.run(['oc', 'delete', 'namespace', ns, '--ignore-not-found'], check=True)
    print('Project retired. GitLab repository archived; workspace PVCs and delivery history retained.')


if __name__ == '__main__': main()
