"""Exact source and completed-operation contract for the Stage 070 component Applications.

Each component (gitops/argocd/app-of-apps/070-advanced-app-platform/*.yaml) is pinned to one reviewed commit and
deployed in its demo.rhoai.io/deploy-order: apply, sync, wait until Synced and Healthy, then the next. Sync waves
order hooks only inside one Application, so this order is what lets the GitLab integration hub run after the
components it wires together, and Developer Hub's catalog hook run after the GitLab mirror holds the commit.
"""
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
import stage_apps

STAGE = '070'
STAGE_DIR = '070-advanced-app-platform'
DESTINATION = {'server': 'https://kubernetes.default.svc', 'namespace': 'openshift-gitops'}
SCOPE = ['gitops/stages/' + STAGE_DIR, 'gitops/argocd/app-of-apps/' + STAGE_DIR,
         'stages/' + STAGE_DIR, 'scripts/shared', 'scripts/platform/require-node-sizing.sh',
         'scripts/platform/render-stage070-charts.py', 'scripts/platform/stage070-charts.lock.json',
         'scripts/platform/build-stage070-platform-tools.sh']


def run(*args, **kwargs):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=60, **kwargs).stdout


def names():
    return stage_apps.names(STAGE)


def manifest(name):
    for app in stage_apps.components(STAGE):
        if app['metadata']['name'] == name:
            return app
    raise ValueError(name + ' is not a Stage 070 component')


def source(revision, repo, name):
    parsed = urlsplit(repo)
    if not re.fullmatch('[0-9a-f]{40}', revision or ''):
        raise ValueError('Stage 070 requires a full immutable commit')
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Repository must be HTTPS without embedded credentials')
    return {'repoURL': repo, 'targetRevision': revision, 'path': manifest(name)['spec']['source']['path']}


def select_revision(ref, repo, root=ROOT):
    commit = run('git', '-C', str(root), 'rev-parse', '--verify', ref + '^{commit}').strip()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Stage 070 requires a full immutable commit')
    run('git', '-C', str(root), 'diff', '--exit-code', commit, '--', *SCOPE)
    if run('git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '--', *SCOPE).strip():
        raise ValueError('Untracked Stage 070 source is not in the selected commit')
    published = {line.split()[0] for line in run('git', 'ls-remote', repo).splitlines()}
    if commit not in published:
        raise ValueError('Selected commit is not advertised by the configured repository')
    return commit


def application(revision, repo, name):
    doc = manifest(name)
    doc['spec']['source'] = source(revision, repo, name)
    return doc


def read(name):
    return json.loads(run('oc', '--request-timeout=15s', 'get', 'application', name,
                          '-n', 'openshift-gitops', '-o', 'json'))


def reconciled(app, revision, repo, name):
    expected = source(revision, repo, name)
    spec = app['spec']; status = app.get('status', {}); op = status.get('operationState', {})
    if (spec.get('project') != 'rhoai-demo' or spec.get('source') != expected or 'sources' in spec
            or spec.get('destination') != DESTINATION):
        raise ValueError(name + ' source or owner changed during deployment')
    operation_revision = op.get('syncResult', {}).get('revision') or op.get('operation', {}).get('sync', {}).get('revision')
    if not app.get('operation') and operation_revision == revision and op.get('phase') in ('Failed', 'Error'):
        raise ValueError(name + ' native operation failed; inspect its hook status')
    return (not app.get('operation') and op.get('phase') == 'Succeeded'
            and op.get('syncResult', {}).get('revision') == revision
            and status.get('sync', {}).get('revision') == revision
            and status.get('sync', {}).get('status') == 'Synced'
            and status.get('health', {}).get('status') == 'Healthy')


def wait(revision, repo, timeout, name, reader=None, clock=time.monotonic, sleep=time.sleep):
    reader = reader or (lambda: read(name))
    deadline = clock() + timeout
    while True:
        if reconciled(reader(), revision, repo, name):
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError(name + ' did not reconcile the selected revision before the deadline')
        sleep(min(10, remaining))


def sync(revision, repo, name):
    app = read(name)
    if (app['spec'].get('source') != source(revision, repo, name) or app['spec'].get('project') != 'rhoai-demo'
            or app['spec'].get('destination') != DESTINATION):
        raise ValueError('Apply the exact ' + name + ' Application before starting sync')
    operation = app.get('operation') or {}
    state = app.get('status', {}).get('operationState', {})
    if operation or state.get('phase') in ('Running', 'Terminating'):
        active = operation or state.get('operation', {})
        if state.get('phase') != 'Terminating' and active.get('sync', {}).get('revision') == revision:
            # Applying a new pin can start auto-sync before this call. Reuse that
            # exact operation instead of submitting a duplicate or failing deploy.
            return
        raise ValueError('A different ' + name + ' operation is active; preserve it and wait')
    patch = {'operation': {'sync': {'revision': revision, 'prune': True,
             'syncOptions': ['ApplyOutOfSyncOnly=false', 'RespectIgnoreDifferences=true', 'ClientSideApplyMigration=false']}}}
    run('oc', '--request-timeout=15s', 'patch', 'application', name, '-n', 'openshift-gitops',
        '--type=merge', '--patch-file=/dev/stdin', input=json.dumps(patch))


def deploy(revision, repo, timeout):
    """Each component in deploy order: apply its pinned Application, run one full sync, wait for it."""
    for name in names():
        run('oc', '--request-timeout=15s', 'apply', '-f', '-', input=json.dumps(application(revision, repo, name)))
        sync(revision, repo, name)
        wait(revision, repo, timeout, name)
        print('PASS ' + name + ' synced and healthy at ' + revision[:12], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['select', 'deploy', 'status'])
    parser.add_argument('--revision')
    parser.add_argument('--repo-url', required=True)
    parser.add_argument('--timeout', type=int, default=3600, help='seconds per component')
    args = parser.parse_args()
    if args.action == 'select':
        print(select_revision(args.revision or 'HEAD', args.repo_url)); return
    if args.action == 'status':
        revision = args.revision or stage_apps.stage_revision(STAGE)
        stale = [name for name in names() if not reconciled(read(name), revision, args.repo_url, name)]
        if stale:
            raise ValueError('Not reconciled at ' + revision + ': ' + ', '.join(stale))
        print('PASS: every Stage 070 component agrees at ' + revision + ' with a completed operation'); return
    deploy(args.revision, args.repo_url, args.timeout)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TimeoutError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
