"""Write generated Secrets without persisting a credential copy in annotations."""
import argparse
import copy
import json
import os
import subprocess
import sys

LAST_APPLIED = 'kubectl.kubernetes.io/last-applied-configuration'


def oc(*args, document=None):
    result = subprocess.run(['oc', *args], input=None if document is None else json.dumps(document), universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def write_secret(document, call=oc):
    doc = copy.deepcopy(document)
    meta = doc.get('metadata', {})
    if doc.get('kind') != 'Secret' or not meta.get('name') or not meta.get('namespace'):
        raise ValueError('An explicitly named, namespaced Secret is required')
    annotations = meta.setdefault('annotations', {})
    annotations.pop(LAST_APPLIED, None)
    # Read first when allowed (writers scoped by resourceNames). A writer that may not read Secrets (create and patch
    # only, so it cannot see the namespace's other Secrets) creates and merge-patches on AlreadyExists instead.
    exists = None
    try:
        call('get', 'secret', meta['name'], '-n', meta['namespace'], '-o', 'json')
        exists = True
    except subprocess.CalledProcessError as error:
        stderr = error.stderr or ''
        if '(NotFound)' in stderr:
            exists = False
        elif '(Forbidden)' not in stderr:
            raise RuntimeError('Secret lookup refused; payload redacted') from None
    if not exists:
        try:
            return call('create', '-f', '-', '-o', 'json', document=doc)
        except subprocess.CalledProcessError as error:
            if '(AlreadyExists)' not in (error.stderr or ''):
                raise RuntimeError('Secret creation refused; payload redacted') from None
    # Merge only the supplied keys, retaining unrelated data and metadata.
    annotations[LAST_APPLIED] = None
    patch = {k: doc[k] for k in ('data', 'stringData', 'type') if k in doc}
    patch['metadata'] = {k: meta[k] for k in ('labels', 'annotations') if k in meta}
    try:
        return call('patch', 'secret', meta['name'], '-n', meta['namespace'],
                    '--type=merge', '--patch-file=/dev/stdin', '-o', 'json', document=patch)
    except subprocess.CalledProcessError:
        raise RuntimeError('Secret update refused; payload redacted') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name')
    parser.add_argument('--namespace')
    parser.add_argument('--from-env', action='append', default=[], metavar='KEY=VARIABLE')
    args = parser.parse_args()
    if args.from_env:
        if not args.name or not args.namespace:
            parser.error('--name and --namespace are required with --from-env')
        values = {}
        for item in args.from_env:
            key, variable = item.split('=', 1)
            values[key] = os.environ[variable]
        doc = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
            'name': args.name, 'namespace': args.namespace}, 'stringData': values}
    else:
        doc = json.load(sys.stdin)
    write_secret(doc)
    print('Secret reconciled without a credential annotation')


if __name__ == '__main__':
    main()
