"""Exact source and completed-operation contract for the existing Stage 070 owner."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/shared'))
from stage_apps import load_yaml_stream

NAME = '070-advanced-app-platform'
DESTINATION = {'server': 'https://kubernetes.default.svc'}
SCOPE = ['gitops/stages/' + NAME, 'gitops/argocd/app-of-apps/' + NAME + '.yaml',
         'stages/' + NAME, 'scripts/shared', 'scripts/platform/require-node-sizing.sh',
         'scripts/platform/render-stage070-charts.py', 'scripts/platform/stage070-charts.lock.json',
         'scripts/platform/build-stage070-platform-tools.sh']


def run(*args, **kwargs):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=60, **kwargs).stdout


def source(revision, repo):
    parsed = urlsplit(repo)
    if not re.fullmatch('[0-9a-f]{40}', revision or ''):
        raise ValueError('Stage 070 requires a full immutable commit')
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Repository must be HTTPS without embedded credentials')
    return {'repoURL': repo, 'targetRevision': revision,
            'path': 'gitops/stages/' + NAME + '/base'}


def select_revision(ref, repo, root=ROOT):
    commit = run('git', '-C', str(root), 'rev-parse', '--verify', ref + '^{commit}').strip()
    source(commit, repo)
    run('git', '-C', str(root), 'diff', '--exit-code', commit, '--', *SCOPE)
    if run('git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '--', *SCOPE).strip():
        raise ValueError('Untracked Stage 070 source is not in the selected commit')
    published = {line.split()[0] for line in run('git', 'ls-remote', repo).splitlines()}
    if commit not in published:
        raise ValueError('Selected commit is not advertised by the configured repository')
    return commit


def application(revision, repo):
    doc = load_yaml_stream((ROOT / 'gitops/argocd/app-of-apps' / (NAME + '.yaml')).read_text())[0]
    doc['spec']['source'] = source(revision, repo)
    return doc


def read():
    return json.loads(run('oc', '--request-timeout=15s', 'get', 'application', NAME,
                          '-n', 'openshift-gitops', '-o', 'json'))


def reconciled(app, revision, repo):
    expected = source(revision, repo)
    spec = app['spec']; status = app.get('status', {}); op = status.get('operationState', {})
    if (spec.get('project') != 'rhoai-demo' or spec.get('source') != expected or 'sources' in spec
            or spec.get('destination') != DESTINATION):
        raise ValueError('Stage 070 source or owner changed during deployment')
    operation_revision = op.get('syncResult', {}).get('revision') or op.get('operation', {}).get('sync', {}).get('revision')
    if not app.get('operation') and operation_revision == revision and op.get('phase') in ('Failed', 'Error'):
        raise ValueError('Stage 070 native operation failed; inspect its hook status')
    return (not app.get('operation') and op.get('phase') == 'Succeeded'
            and op.get('syncResult', {}).get('revision') == revision
            and status.get('sync', {}).get('revision') == revision
            and status.get('sync', {}).get('status') == 'Synced'
            and status.get('health', {}).get('status') == 'Healthy')


def wait(revision, repo, timeout, reader=read, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while True:
        if reconciled(reader(), revision, repo):
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('Stage 070 did not reconcile the selected revision before the deadline')
        sleep(min(10, remaining))


def sync(revision, repo):
    app = read()
    if (app['spec'].get('source') != source(revision, repo) or app['spec'].get('project') != 'rhoai-demo'
            or app['spec'].get('destination') != DESTINATION):
        raise ValueError('Apply the exact Stage 070 Application before starting sync')
    operation = app.get('operation') or {}
    state = app.get('status', {}).get('operationState', {})
    if operation or state.get('phase') in ('Running', 'Terminating'):
        active = operation or state.get('operation', {})
        if state.get('phase') != 'Terminating' and active.get('sync', {}).get('revision') == revision:
            # Applying a new pin can start auto-sync before this call. Reuse that
            # exact operation instead of submitting a duplicate or failing deploy.
            return
        raise ValueError('A different Stage 070 operation is active; preserve it and wait')
    patch = {'operation': {'sync': {'revision': revision, 'prune': True,
             'syncOptions': ['ApplyOutOfSyncOnly=false', 'RespectIgnoreDifferences=true', 'ClientSideApplyMigration=false']}}}
    run('oc', '--request-timeout=15s', 'patch', 'application', NAME, '-n', 'openshift-gitops',
        '--type=merge', '--patch-file=/dev/stdin', input=json.dumps(patch))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['select', 'render', 'sync', 'wait', 'status'])
    parser.add_argument('--revision')
    parser.add_argument('--repo-url', required=True)
    parser.add_argument('--timeout', type=int, default=3600)
    args = parser.parse_args()
    if args.action == 'select':
        print(select_revision(args.revision or 'HEAD', args.repo_url)); return
    if args.action == 'status':
        app = read(); revision = args.revision or app['spec'].get('source', {}).get('targetRevision')
        if not reconciled(app, revision, args.repo_url):
            raise ValueError('Stage 070 is not reconciled at its pinned revision')
        print('PASS: Stage 070 source and completed operation agree at ' + revision); return
    source(args.revision, args.repo_url)
    if args.action == 'render': print(json.dumps(application(args.revision, args.repo_url)))
    elif args.action == 'sync': sync(args.revision, args.repo_url)
    else: wait(args.revision, args.repo_url, args.timeout)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TimeoutError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
