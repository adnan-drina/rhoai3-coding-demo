#!/usr/bin/env python3
"""Execute the shipped Task shell against a concurrent, persistent fake API.

Exercises duplicate delivery, provision/retire overlap, interrupted retirement,
API failures, credential preservation and tombstones. This is not a live-cluster
qualification. The fake implements atomic create, and logs all mutations.
"""
import base64
import fcntl
import json
import itertools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import textwrap

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'scaffold-repo/quarkus-migration-scaffold/.hermes/lib'))
from planner.yamlite import loads as yaml_loads

TASK = HERE.parents[1] / 'gitops/stages/050-advanced-app-platform/base/pipelines/build/task-provision-migration-run.yaml'


def fake_oc():
    args = [a for a in sys.argv[2:] if not a.startswith("--request-timeout=")]
    home = Path(os.environ['FAKE_API'])
    verb, kind = args[:2]
    names = {
        'configmap': 'ConfigMap', 'secret': 'Secret', 'deployment': 'Deployment',
        'service': 'Service', 'serviceaccount': 'ServiceAccount', 'sa': 'ServiceAccount',
        'role': 'Role', 'rolebinding': 'RoleBinding',
    }
    name = args[2] if len(args) > 2 and not args[2].startswith('-') else ''
    def option(flag, default=''):
        for i, a in enumerate(args):
            if a == flag:
                return args[i + 1]
            if a.startswith(flag + '='):
                return a.split('=', 1)[1]
        return default
    receipt = 'migration-run-demo-v10'
    if verb == 'get' and name == receipt and os.environ.get('FAKE_HOLD'):
        (home / 'held').touch()
        until = time.monotonic() + 20
        while not (home / 'release').exists():
            if time.monotonic() > until:
                return 43
            time.sleep(.02)
    if verb == 'get' and name == os.environ.get('FAKE_FAIL_GET'):
        print('Forbidden', file=sys.stderr)
        return 42
    if verb == 'delete' and kind == os.environ.get('FAKE_FAIL_DELETE'):
        return 42
    incoming = None
    if verb == 'apply':
        raw = sys.stdin.read()
        incoming = json.loads(raw) if raw.lstrip().startswith('{') else yaml_loads(raw)
    with (home / 'mutex').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((home / 'state.json').read_text())
        objects = state['objects']
        key = names.get(kind, kind) + '/' + name
        result = ''
        changed = False
        if verb == 'create':
            data = dict(a.split('=', 1)[1].split('=', 1) for a in args if a.startswith('--from-literal='))
            obj = {'apiVersion': 'v1', 'kind': names[kind], 'metadata': {'name': name}, 'data': data}
            if '--dry-run=client' in args:
                print(json.dumps(obj))
                return 0
            if key in objects:
                print('AlreadyExists', file=sys.stderr)
                return 1
            objects[key] = obj
            changed = True
        elif verb == 'apply':
            obj = incoming
            if obj['kind'] == 'Secret' and 'stringData' in obj:
                obj['data'] = {k: base64.b64encode(str(v).encode()).decode() for k, v in obj.pop('stringData').items()}
            key = obj['kind'] + '/' + obj['metadata']['name']
            objects[key] = obj
            changed = True
        elif verb == 'delete':
            selected = option('-l')
            for k in list(objects):
                obj = objects[k]
                labels = obj['metadata'].get('labels', {})
                match = selected and labels.get(selected.split('=', 1)[0]) == selected.split('=', 1)[1]
                if (selected and obj['kind'] == names[kind] and match) or (not selected and k == key):
                    del objects[k]
                    changed = True
        elif verb == 'get':
            if ',' in kind:
                selected = option('-l')
                lk, lv = selected.split('=', 1)
                wanted = tuple(names.get(k.strip(), k.strip()) for k in kind.split(','))
                result = '\n'.join(k for k, obj in objects.items()
                                   if obj['kind'] in wanted and obj['metadata'].get('labels', {}).get(lk) == lv)
            elif key not in objects:
                if '--ignore-not-found' not in args:
                    print('NotFound', file=sys.stderr)
                    return 1
            else:
                obj = objects[key]
                fmt = option('-o')
                data = obj.get('data', {})
                if fmt == 'name':
                    result = key
                elif fmt.startswith('jsonpath='):
                    result = str(data.get(fmt.split('.data.', 1)[1].split('}', 1)[0], ''))
                elif 'range $k' in fmt:
                    result = '\n'.join(data)
                elif 'index .data' in fmt:
                    result = data[fmt.split('"')[1]]
                else:
                    raise AssertionError(fmt)
        elif verb == 'label':
            pass
        else:
            raise AssertionError(args)
        if changed:
            state['mutations'].append({'task': os.environ['TASKRUN'], 'verb': verb, 'key': key})
        (home / 'state.json').write_text(json.dumps(state))
        if result:
            print(result)
    return 0


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / 'state.json').write_text(json.dumps({'objects': {'Secret/fixtures': {
            'kind': 'Secret', 'metadata': {'name': 'fixtures'}, 'data': {'IDENTITY': 'eDp5'}}}, 'mutations': []}))
        oc = self.home / 'oc'
        oc.write_text('#!/bin/sh\nexec ' + sys.executable + ' ' + str(Path(__file__).resolve()) + ' fake "$@"\n')
        oc.chmod(0o755)
        script = textwrap.dedent('\n'.join(itertools.takewhile(
            lambda line: not line.strip() or line.startswith('        '),
            TASK.read_text().split('      script: |\n', 1)[1].splitlines())))
        self.assertIn('$(results.receipt.path)', script)
        for key in ('outcome','receipt'):
            script = script.replace('$(results.' + key + '.path)', str(self.home / key))
        self.script = self.home / 'task.sh'
        self.script.write_text(script)
        self.env = dict(os.environ, PATH=str(self.home) + ':' + os.environ['PATH'], FAKE_API=str(self.home),
                        RUN='demo-v10', WSNS='test-ns', SCAFFOLD='a'*40, FIXTURE_SRC='fixtures',
                        DB_IMAGE='registry.test/db@sha256:'+'a'*64, CLI_IMAGE='registry.test/cli@sha256:'+'b'*64)

    def start(self, mode='provision', task='test', **extra):
        return subprocess.Popen(['bash', str(self.script)], env=dict(self.env, MODE=mode, TASKRUN=task, **extra),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def finish(self, proc, success=True):
        out, err = proc.communicate(timeout=30)
        if success:
            self.assertEqual(proc.returncode, 0, out + err)
        else:
            self.assertNotEqual(proc.returncode, 0, out + err)
        return out + err

    def objects(self):
        return json.loads((self.home / 'state.json').read_text())['objects']

    def test_redelivery_preserves_credentials_and_retirement_is_final(self):
        self.finish(self.start())
        first = self.objects()['Secret/demo-v10-parity-postgres']['data']
        self.finish(self.start(task='redelivery'))
        self.assertEqual(first, self.objects()['Secret/demo-v10-parity-postgres']['data'])
        self.finish(self.start('retire'))
        self.finish(self.start(task='late'), False)
        self.assertEqual(self.objects()['ConfigMap/migration-run-demo-v10']['data']['phase'], 'retired')
        self.assertFalse(any('/demo-v10-parity' in k for k in self.objects()))
        self.assertFalse(any(k.endswith('/demo-v10-worker') for k in self.objects()))

    def overlap(self, second_mode):
        first = self.start(task='first', FAKE_HOLD='1')
        until = time.monotonic() + 10
        while not (self.home / 'held').exists():
            self.assertLess(time.monotonic(), until)
            time.sleep(.02)
        second = self.start(second_mode, task='second')
        time.sleep(.3)
        self.assertIsNone(second.poll(), 'second writer did not wait for the lock')
        (self.home / 'release').touch()
        self.finish(first)
        self.finish(second)

    def test_overlapping_retirement_cannot_be_overwritten(self):
        self.overlap('retire')
        self.assertEqual(self.objects()['ConfigMap/migration-run-demo-v10']['data']['phase'], 'retired')
        self.assertFalse(any('/demo-v10-parity' in k for k in self.objects()))
        self.assertFalse(any(k.endswith('/demo-v10-worker') for k in self.objects()))

    def test_concurrent_duplicate_delivery(self):
        self.overlap('provision')
        self.assertEqual(self.objects()['ConfigMap/migration-run-demo-v10']['data']['phase'], 'provisioned')
        server = self.objects()['Secret/demo-v10-parity-postgres']['data']['database-password']
        workspace = self.objects()['Secret/demo-v10-parity-db']['data']['PETCLINIC_DB_PASSWORD']
        self.assertEqual(server, workspace)

    def test_worker_identity_is_created_and_retired(self):
        self.finish(self.start())
        objects = self.objects()
        for kind in ('ServiceAccount', 'Role', 'RoleBinding'):
            obj = objects['%s/demo-v10-worker' % kind]
            self.assertEqual(obj['metadata']['labels']['rhoai3.io/migration-run'], 'demo-v10')
        role = objects['Role/demo-v10-worker']
        verbs = {(tuple(r.get('resources') or []), tuple(r.get('verbs') or []),
                  tuple(r.get('resourceNames') or []), tuple(r.get('apiGroups') or ['']))
                 for r in role['rules']}
        self.assertIn((('configmaps',), ('get',), ('devspace-ai-tools-init',), ('',)), verbs)
        self.assertIn((('securitycontextconstraints',), ('use',), ('container-build',),
                       ('security.openshift.io',)), verbs)
        self.assertEqual(objects['ConfigMap/migration-run-demo-v10']['data']['workerServiceAccount'],
                         'demo-v10-worker')
        self.finish(self.start('retire'))
        self.assertFalse(any(k.endswith('/demo-v10-worker') for k in self.objects()))

    def test_api_failure_is_not_absence(self):
        for name in ('migration-run-demo-v10','demo-v10-parity-postgres'):
            self.finish(self.start(FAKE_FAIL_GET=name), False)
            self.assertEqual(list(self.objects()), ['Secret/fixtures'])

    def test_interrupted_retirement_keeps_durable_intent(self):
        self.finish(self.start())
        self.finish(self.start('retire', FAKE_FAIL_DELETE='deployment'), False)
        self.assertEqual(self.objects()['ConfigMap/migration-run-demo-v10']['data']['phase'], 'retiring')
        self.finish(self.start(), False)
        self.finish(self.start('retire'))

    def test_incomplete_existing_secret_is_not_rotated(self):
        state = json.loads((self.home / 'state.json').read_text())
        state['objects']['Secret/demo-v10-parity-postgres'] = {
            'kind': 'Secret', 'metadata': {'name': 'demo-v10-parity-postgres'}, 'data': {}}
        (self.home / 'state.json').write_text(json.dumps(state))
        self.finish(self.start(), False)
        self.assertEqual(self.objects()['Secret/demo-v10-parity-postgres']['data'], {})

    def test_unpinned_image_cannot_create_resources(self):
        self.finish(self.start(DB_IMAGE='registry.test/db:latest'), False)
        self.assertEqual(list(self.objects()), ['Secret/fixtures'])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'fake':
        sys.exit(fake_oc())
    unittest.main()
