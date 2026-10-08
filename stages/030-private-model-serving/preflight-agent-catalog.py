#!/usr/bin/env python3
"""Refuse foreign catalog content before the Stage 030 Application write."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NAME = "agent-catalog-sources"
NS = "rhoai-model-registries"
TRACKING = f"030-private-model-serving:/ConfigMap:{NS}/{NAME}"


def check_rbac(existing, desired):
    metadata = desired['metadata']
    name, kind = metadata['name'], desired['kind']
    if metadata.get('namespace') != 'demo-sandbox' or name not in ['mcp-registry-admins', 'mcp-registry-readers'] or kind not in ['Role', 'RoleBinding']:
        raise RuntimeError('Registry metadata RBAC identity differs')
    if kind == 'Role':
        verbs = ['get', 'list', 'create', 'update', 'delete'] if name.endswith('admins') else ['get', 'list']
        if desired.get('rules') != [{'apiGroups': ['mlflow.kubeflow.org'], 'resources': ['mcpservers'], 'verbs': verbs}]:
            raise RuntimeError('Registry RBAC must cover only native MCP metadata')
    else:
        group = 'rhods-admins' if name.endswith('admins') else 'rhoai-developers'
        if desired.get('roleRef') != {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name} or desired.get('subjects') != [{'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Group', 'name': group}]:
            raise RuntimeError('Registry metadata RBAC subject or reference differs')
    if existing is None:
        return
    actual = existing['metadata']
    expected_tracking = f'030-private-model-serving:rbac.authorization.k8s.io/{kind}:demo-sandbox/{name}'
    if existing.get('kind') != kind or actual.get('name') != name or actual.get('namespace') != 'demo-sandbox' or actual.get('ownerReferences') or actual.get('deletionTimestamp') or actual.get('annotations', {}).get('argocd.argoproj.io/tracking-id') != expected_tracking:
        raise RuntimeError('Registry metadata RBAC is foreign-owned or terminating')
    if kind == 'RoleBinding' and existing.get('roleRef') != desired['roleRef']:
        raise RuntimeError('Existing registry RoleBinding has a different immutable reference')


def check(existing, desired):
    data = desired.get('data', {})
    if set(data) != {'sources.yaml', 'governed-coding-agents.yaml'}:
        raise RuntimeError('Desired catalog file inventory differs')
    parsed = subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(JSON.parse(STDIN.read).transform_values { |v| YAML.safe_load(v) })'], input=json.dumps(data), text=True, capture_output=True, timeout=10)
    if parsed.returncode:
        raise RuntimeError('Desired catalog YAML is invalid')
    catalogs = json.loads(parsed.stdout)
    if catalogs['sources.yaml'] != {'agent_catalogs': [{'id': 'governed-coding-agents', 'name': 'Governed Coding Agents', 'type': 'yaml', 'enabled': True, 'properties': {'yamlCatalogPath': 'governed-coding-agents.yaml'}, 'labels': ['coding', 'governed-runtime']}]}:
        raise RuntimeError('Desired source ID/path/schema differs')
    agents = catalogs['governed-coding-agents.yaml'].get('agents', [])
    if {a.get('name') for a in agents} != {'opencode', 'hermes'} or len(agents) != 2 or any(not a.get('readme') or a.get('templates') or a.get('artifacts') for a in agents):
        raise RuntimeError('Desired agent cards must be the two reviewed metadata-only entries')
    if existing is None:
        return
    metadata = existing["metadata"]
    if existing.get("kind") != "ConfigMap" or metadata.get("name") != NAME or metadata.get("namespace") != NS:
        raise RuntimeError("Catalog configuration identity differs")
    if metadata.get("ownerReferences") or metadata.get("deletionTimestamp") or existing.get("immutable"):
        raise RuntimeError("Catalog configuration is native-owned, terminating, or immutable")
    tracking = metadata.get("annotations", {}).get("argocd.argoproj.io/tracking-id")
    data = existing.get("data", {})
    if tracking == TRACKING:
        return
    if tracking or existing.get("binaryData") or set(data) != {"sources.yaml"}:
        raise RuntimeError("Foreign catalog configuration requires reviewed merge")
    # The installed catalog provides an empty customer source ConfigMap. Only
    # this exact empty shape may be adopted; default catalogs are separate.
    result = subprocess.run(["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.safe_load(STDIN.read))"], input=data["sources.yaml"], text=True, capture_output=True, timeout=10)
    if result.returncode or json.loads(result.stdout) != {"agent_catalogs": []}:
        raise RuntimeError("Existing custom agent sources cannot be overwritten")


def main():
    desired = json.loads(subprocess.check_output(["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_file(ARGV[0]))", str(ROOT / "gitops/stages/030-private-model-serving/base/model-discovery/agent-catalog-sources.yaml")], text=True, timeout=10))
    check(None, desired)
    guard = 'set -euo pipefail; set +x; source "$1/scripts/shared/lib.sh"; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env >/dev/null; check_oc_logged_in >/dev/null; python3 -c "import os,json; print(json.dumps({k:os.environ[k] for k in (\'KUBECONFIG\',\'PATH\',\'HOME\',\'RHOAI_EXPECTED_API_SERVER\') if k in os.environ}))"'
    checked = subprocess.run(["/bin/bash", "-c", guard, "guard", str(ROOT)], capture_output=True, text=True, timeout=45)
    if checked.returncode:
        raise RuntimeError("Project cluster guard failed")
    env = {**os.environ, **json.loads(checked.stdout)}
    project = subprocess.run(['oc', '--request-timeout=10s', 'get', 'namespace', 'demo-sandbox', '-o', 'json'], env=env, capture_output=True, text=True, timeout=20)
    if project.returncode or json.loads(project.stdout)['metadata'].get('deletionTimestamp'):
        raise RuntimeError('Stage 010 demo-sandbox project must exist and be active before registry access is configured')
    folder = ROOT / 'gitops/stages/030-private-model-serving/base/model-discovery/registry'
    for kind in ['Role', 'RoleBinding']:
        for suffix in ['admins', 'readers']:
            file = folder / f'{kind.lower()}-mcp-registry-{suffix}.yaml'
            role = json.loads(subprocess.check_output(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(file)], text=True, timeout=10))
            check_rbac(None, role)
            read = subprocess.run(['oc', '--request-timeout=10s', 'get', kind.lower() + 's.rbac.authorization.k8s.io', role['metadata']['name'], '-n', 'demo-sandbox', '--ignore-not-found', '-o', 'json'], env=env, text=True, capture_output=True, timeout=20)
            if read.returncode:
                raise RuntimeError('Registry metadata RBAC API read failed')
            check_rbac(json.loads(read.stdout) if read.stdout.strip() else None, role)
    namespace = subprocess.run(["oc", "--request-timeout=10s", "get", "namespace", NS, "--ignore-not-found", "-o", "json"], env=env, text=True, capture_output=True, timeout=20)
    if namespace.returncode:
        raise RuntimeError("Catalog namespace API read failed")
    if not namespace.stdout.strip():
        print("[PASS] Agent catalog namespace absent; clean installation")
        return
    result = subprocess.run(["oc", "--request-timeout=10s", "get", "configmap", NAME, "-n", NS, "--ignore-not-found", "-o", "json"], env=env, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError("Catalog configuration API read failed")
    check(json.loads(result.stdout) if result.stdout.strip() else None, desired)
    print("[PASS] Agent catalog source ownership/content preflight")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("[FAIL] " + str(error))
        raise SystemExit(1)
