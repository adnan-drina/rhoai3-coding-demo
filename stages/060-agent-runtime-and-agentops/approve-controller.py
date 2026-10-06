#!/usr/bin/env python3
"""Inventory the selected native OLM plan; approval requires its reviewed digest."""
import argparse
import base64
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

CSV = 'agent-sandbox-operator.v0.9.0'
NS = 'agent-sandbox-system'
APP = 'openshell-runtime'
REPO = 'https://github.com/adnan-drina/rhoai3-coding-demo.git'
SOURCE = 'gitops/stages/060-agent-runtime-and-agentops/runtime'
ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=15s', *args], capture_output=True, text=True)
    require(result.returncode == 0, 'Bounded Kubernetes request failed: ' + args[0])
    return json.loads(result.stdout)


def check_bindings(inventory):
    roles = {(x['kind'], x['metadata'].get('namespace', NS) if x['kind'] == 'Role' else '', x['metadata']['name']): x for x in inventory if x['kind'] in ('Role', 'ClusterRole')}
    bindings = []
    for resource in inventory:
        if resource['kind'] not in ('RoleBinding', 'ClusterRoleBinding'):
            continue
        namespace = resource['metadata'].get('namespace', NS)
        reference = resource.get('roleRef', {})
        require(reference.get('apiGroup') == 'rbac.authorization.k8s.io', 'Unexpected binding API group')
        kind = reference.get('kind')
        require(kind in ('Role', 'ClusterRole') and (resource['kind'] != 'ClusterRoleBinding' or kind == 'ClusterRole'), 'Unexpected binding role kind')
        key = (kind, namespace if kind == 'Role' else '', reference.get('name'))
        require(key in roles, 'Binding references an external/uninventoried role; approval blocked')
        require(resource.get('subjects'), 'Binding subjects missing')
        for subject in resource['subjects']:
            require(subject.get('kind') == 'ServiceAccount' and subject.get('apiGroup', '') == '' and subject.get('namespace', namespace) == NS and subject.get('name'), 'Binding grants an unexpected principal')
        bindings.append({'kind': resource['kind'], 'name': resource['metadata']['name'], 'roleRef': reference, 'subjects': resource['subjects']})
    return bindings


def resolve_entries(entries):
    inventory = []
    provenance = []
    references = [json.loads(x['resource']['manifest']) for x in entries]
    if not any(x.get('kind') == 'ConfigMap' and 'catalogSourceName' in x for x in references):
        return references, provenance
    require(all(x == references[0] for x in references), 'Mixed native bundle references')
    ref = references[0]
    require(ref.get('kind') == 'ConfigMap' and ref.get('namespace') == 'openshift-marketplace' and ref.get('catalogSourceName') == 'redhat-operators' and ref.get('catalogSourceNamespace') == 'openshift-marketplace' and re.fullmatch('[0-9a-f]{63}', ref.get('name', '')), 'Unexpected native bundle reference')
    cm = oc('get', 'configmap', ref['name'], '-n', ref['namespace'], '-o', 'json')
    meta = cm['metadata']
    require(meta['name'] == ref['name'] and meta['namespace'] == ref['namespace'] and meta.get('uid') and not meta.get('deletionTimestamp'), 'Bundle ConfigMap identity mismatch')
    catalog = oc('get', 'catalogsource', 'redhat-operators', '-n', 'openshift-marketplace', '-o', 'json')
    require(any(x.get('kind') == 'CatalogSource' and x.get('apiVersion') == 'operators.coreos.com/v1alpha1' and x.get('name') == 'redhat-operators' and x.get('uid') == catalog['metadata']['uid'] for x in meta.get('ownerReferences', [])), 'Bundle CatalogSource ownership mismatch')
    annotations = meta.get('annotations', {})
    require(annotations.get('olm.contentEncoding') == 'gzip+base64' and annotations.get('operators.operatorframework.io.bundle.package.v1') == 'agent-sandbox-operator' and annotations.get('olm.sourceImage') == 'registry.redhat.io/agent-sandbox/agent-sandbox-operator-bundle@sha256:01f8fbf2cda6e5cbac5c53f9037a8142a1139000f947627404d4c95ee2a2fe2d', 'Native bundle encoding/package/image mismatch')
    require(not cm.get('data') and cm.get('binaryData'), 'Unexpected bundle data representation')
    try:
        import yaml
    except ImportError:
        raise RuntimeError('PyYAML is required to inspect native bundle YAML')
    objects = [yaml.safe_load(gzip.decompress(base64.b64decode(base64.b64decode(value, validate=True), validate=True))) for value in cm['binaryData'].values()]
    csvs = [x for x in objects if x.get('kind') == 'ClusterServiceVersion']
    require(len(csvs) == 1 and csvs[0]['metadata']['name'] == CSV and csvs[0]['spec']['version'] == '0.9.0', 'Native bundle CSV mismatch')
    install = csvs[0]['spec']['install']['spec']
    require(not install.get('permissions') and len(install.get('clusterPermissions', [])) == 1, 'Unexpected generated native permission shape')
    permission = install['clusterPermissions'][0]
    require(permission['serviceAccountName'] == 'agent-sandbox-controller', 'Unexpected native controller principal')
    # OLM generates these three operands from the single native CSV permission block.
    # Use only names declared in the selected plan, retaining the original refs in digest.
    roles = [x['resource'] for x in entries if x['resource']['kind'] == 'ClusterRole']
    bindings = [x['resource'] for x in entries if x['resource']['kind'] == 'ClusterRoleBinding']
    require(len(roles) == len(bindings) == 1 and roles[0]['name'] == bindings[0]['name'] and roles[0]['name'].startswith('agent-sandbox-operator.v-'), 'Unexpected generated native role pairing')
    for entry in entries:
        resource = entry['resource']
        matches = [x for x in objects if x['kind'] == resource['kind'] and x['metadata']['name'] == resource['name']]
        if not matches:
            require(resource['kind'] in ('ServiceAccount', 'ClusterRole', 'ClusterRoleBinding'), 'Missing native bundle object')
            obj = {'apiVersion': (resource['group'] + '/' if resource['group'] else '') + resource['version'], 'kind': resource['kind'], 'metadata': {'name': resource['name']}}
            if resource['kind'] == 'ServiceAccount':
                require(resource['name'] == permission['serviceAccountName'], 'Unexpected generated native ServiceAccount')
                obj['metadata']['namespace'] = NS
            elif resource['kind'] == 'ClusterRole':
                obj['rules'] = permission['rules']
            else:
                obj['roleRef'] = {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': roles[0]['name']}
                obj['subjects'] = [{'kind': 'ServiceAccount', 'name': permission['serviceAccountName'], 'namespace': NS}]
            matches = [obj]
        require(len(matches) == 1, 'Ambiguous native bundle resource')
        inventory.append(matches[0])
    require(all(any(x['kind'] == y['kind'] and x['metadata']['name'] == y['metadata']['name'] for y in inventory) for x in objects), 'Bundle contains unplanned resources')
    provenance.append({'references': references, 'configmap': {'name': meta['name'], 'namespace': meta['namespace'], 'uid': meta['uid'], 'ownerReferences': meta.get('ownerReferences'), 'annotations': annotations, 'binaryData': cm['binaryData']}, 'catalog_uid': catalog['metadata']['uid']})
    return inventory, provenance


def run(args):
    require(re.fullmatch('[0-9a-f]{40}', args.revision), 'Expected revision must be a published 40-character SHA')
    guard = subprocess.run(['bash', '-c', 'REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; test -n "${RHOAI_EXPECTED_API_SERVER:-}"; check_oc_logged_in', 'stage060-controller-guard', str(ROOT)], capture_output=True, text=True)
    require(guard.returncode == 0, 'Shared environment/login guard failed; expected cluster identifier is required')
    published = subprocess.run(['git', '-C', str(ROOT), 'show', args.revision + ':' + str(Path(__file__).resolve().relative_to(ROOT))], capture_output=True)
    require(published.returncode == 0 and published.stdout == Path(__file__).read_bytes(), 'Helper must match selected published revision')
    remote = subprocess.run(['git', 'ls-remote', REPO, 'refs/heads/codex/stage-010-foundation-35'], capture_output=True, text=True, timeout=30)
    require(remote.returncode == 0 and remote.stdout.split() == [args.revision, 'refs/heads/codex/stage-010-foundation-35'], 'Selected SHA is not the published reviewed branch head')
    app = oc('get', 'application', APP, '-n', 'openshift-gitops', '-o', 'json')
    spec = app['spec']
    source = {'repoURL': REPO, 'path': SOURCE, 'targetRevision': args.revision}
    require(not app['metadata'].get('deletionTimestamp') and not app['metadata'].get('ownerReferences') and not spec.get('sources'), 'Unexpected runtime Application lifecycle/source')
    require(spec.get('project') == 'rhoai-demo' and all(spec.get('source', {}).get(k) == v for k, v in source.items()), 'Runtime Application source mismatch')
    require(spec.get('destination') == {'server': 'https://kubernetes.default.svc', 'namespace': 'openshell'}, 'Runtime Application destination mismatch')
    operation = app.get('status', {}).get('operationState', {})
    sync = operation.get('syncResult', {})
    require(operation.get('phase') in ('Running', 'Succeeded') and sync.get('revision') == args.revision, 'Runtime operation is not at selected revision')
    require(all(sync.get('source', {}).get(k) == v for k, v in source.items()), 'Runtime operation source mismatch')
    sub = oc('get', 'subscription', 'agent-sandbox-operator', '-n', NS, '-o', 'json')
    require(all(sub['spec'].get(k) == v for k, v in {'name': 'agent-sandbox-operator', 'channel': 'preview-0.9', 'source': 'redhat-operators', 'sourceNamespace': 'openshift-marketplace', 'startingCSV': CSV, 'installPlanApproval': 'Manual'}.items()), 'Selected Subscription tuple mismatch')
    require(not sub['metadata'].get('ownerReferences') and not sub['metadata'].get('deletionTimestamp') and sub['metadata'].get('annotations', {}).get('argocd.argoproj.io/tracking-id') == APP + ':operators.coreos.com/Subscription:' + NS + '/agent-sandbox-operator', 'Subscription is not owned by expected runtime Application')
    ref = sub.get('status', {}).get('installPlanRef', {})
    require(ref.get('name') and ref.get('namespace', NS) == NS, 'Selected InstallPlan reference missing/mismatched')
    plan = oc('get', 'installplan', ref['name'], '-n', NS, '-o', 'json')
    require(any(x.get('uid') == sub['metadata']['uid'] and x.get('kind') == 'Subscription' for x in plan['metadata'].get('ownerReferences', [])), 'InstallPlan owner mismatch')
    require(plan['spec'].get('approval') == 'Manual' and plan['spec'].get('clusterServiceVersionNames') == [CSV], 'Unexpected InstallPlan family')
    entries = plan.get('status', {}).get('plan', [])
    require(entries, 'InstallPlan permission inventory is unavailable')
    inventory, provenance = resolve_entries(entries)
    selected = []
    for entry, manifest in zip(entries, inventory):
        resource = entry['resource']
        require(entry.get('resolving') == CSV, 'InstallPlan contains an unexpected dependency')
        require(manifest.get('kind') == resource['kind'] and manifest.get('metadata', {}).get('name') == resource['name'] and manifest.get('apiVersion') == (resource.get('group', '') + '/' if resource.get('group') else '') + resource['version'], 'Plan resource GVK/name mismatch')
        if resource['kind'] == 'ClusterServiceVersion':
            require(resource['name'] == CSV and manifest['spec'].get('version') == '0.9.0', 'Unexpected CSV version')
            selected.append(manifest)
    require(len(selected) == 1, 'Exactly one selected CSV must be inventoried')
    # Inspect every nested rule and pod security field, including the CSV install strategy.
    def inspect(value):
        if isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, dict):
            if 'verbs' in value:
                require(not set(value['verbs']) & {'*', 'use', 'bind', 'escalate', 'impersonate'}, 'Unexpected privileged RBAC verb; native requirement needs explicit review')
                require('*' not in value.get('apiGroups', []) and '*' not in value.get('resources', []) and not value.get('nonResourceURLs'), 'Unexpected wildcard/non-resource permission')
                require('security.openshift.io' not in value.get('apiGroups', []) and 'securitycontextconstraints' not in value.get('resources', []), 'Unexpected SCC permission')
            for key in ('privileged', 'hostNetwork', 'hostPID', 'hostIPC', 'allowPrivilegeEscalation'):
                require(value.get(key) is not True, 'Unexpected privileged workload setting: ' + key)
            caps = value.get('capabilities', {})
            require('hostPath' not in value and not (isinstance(caps, dict) and caps.get('add')), 'Unexpected host mount or added capability')
            require(value.get('runAsUser') != 0, 'Unexpected root workload')
            for item in value.values():
                inspect(item)
    # CRD OpenAPI property definitions describe fields; they are not deployed Pod settings.
    # Their complete bytes remain in the reviewed digest.
    inspect([r for r in inventory if r['kind'] != 'CustomResourceDefinition'])
    bindings = check_bindings(inventory)
    # Hash the complete native plan, not just a subset of permissions. Never print manifests:
    # ConfigMaps or Secret-bearing operands could carry private material.
    encoded = json.dumps({'plan_uid': plan['metadata']['uid'], 'resources': sorted(inventory, key=lambda x: (x['kind'], x['metadata']['name'])), 'native_bundle_provenance': provenance}, sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    install = selected[0]['spec']['install']['spec']
    images = sorted({container['image'] for deployment in install.get('deployments', []) for container in deployment['spec']['template']['spec'].get('containers', []) + deployment['spec']['template']['spec'].get('initContainers', [])})
    print(json.dumps({'bindings': bindings, 'controller_images': images, 'related_images': selected[0]['spec'].get('relatedImages', []), 'csv': CSV, 'plan': plan['metadata']['name'], 'plan_sha256': digest, 'permissions': install.get('permissions', []), 'clusterPermissions': install.get('clusterPermissions', []), 'resource_kinds': sorted({x['kind'] for x in inventory}), 'approved': plan['spec'].get('approved', False)}, indent=2))
    if args.approve:
        require(args.reviewed_plan_sha256 == digest, 'Approval requires the exact independently reviewed plan digest')
        if not plan['spec'].get('approved', False):
            patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': plan['metadata']['resourceVersion']}, {'op': 'test', 'path': '/spec/approved', 'value': False}, {'op': 'replace', 'path': '/spec/approved', 'value': True}]
            result = subprocess.run(['oc', '--request-timeout=15s', 'patch', 'installplan', plan['metadata']['name'], '-n', NS, '--type=json', '--patch-file=/dev/stdin', '-o', 'name'], input=json.dumps(patch), text=True, capture_output=True)
            require(result.returncode == 0, 'InstallPlan approval failed; re-inventory before retrying')
            print('Selected native InstallPlan approved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--approve', action='store_true')
    parser.add_argument('--reviewed-plan-sha256')
    try:
        run(parser.parse_args())
    except (RuntimeError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + '\n')
