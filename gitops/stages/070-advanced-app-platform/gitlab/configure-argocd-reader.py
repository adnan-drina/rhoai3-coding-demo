"""Reconcile the canonical portal/delivery read account without replacing RBAC."""
import json
import subprocess
import time

RULES = ['p, role:rhdh-reader, applications, get, rhoai-demo/*, allow',
         'p, role:rhdh-reader, applications, get, runtime-projects/*, allow',
         'p, role:rhdh-reader, applications, get, platform-projects/*, allow',
         'g, rhdh, role:rhdh-reader']


def policy(existing):
    rows = existing.splitlines()
    for row in RULES:
        if row not in rows: rows.append(row)
    return '\n'.join(rows) + '\n'


def main():
    # A missing Deny parameter blocks even unrelated Application updates before
    # match conditions run. Initialize a denying record before wave-12 policies.
    initial = {'apiVersion':'v1','kind':'ConfigMap',
               'metadata':{'name':'stage070-project-release','namespace':'openshift-gitops'},
               'data':{'ready':'false','repo_url':'__not_ready__','revision':'__not_ready__','delivery_base_url':'__not_ready__'}}
    result = subprocess.run(['oc','create','-f','-'],input=json.dumps(initial),
                            universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode and '(AlreadyExists)' not in result.stderr:
        raise RuntimeError('Could not initialize fail-closed enrollment parameters: ' + result.stderr)
    resource = json.loads(subprocess.check_output(['oc', 'get', 'argocd', 'openshift-gitops',
        '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True))
    spec = resource['spec']
    patch = {'spec': {'extraConfig': {'accounts.rhdh': 'apiKey'},
                     'rbac': {'policy': policy(spec.get('rbac', {}).get('policy', ''))}}}
    subprocess.run(['oc', 'patch', 'argocd', 'openshift-gitops', '-n', 'openshift-gitops',
                    '--type=merge', '-p', json.dumps(patch)], check=True)
    for _ in range(60):
        account = subprocess.check_output(['oc', 'get', 'configmap', 'argocd-cm',
            '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True)
        rbac = subprocess.check_output(['oc', 'get', 'configmap', 'argocd-rbac-cm',
            '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True)
        if json.loads(account)['data'].get('accounts.rhdh') == 'apiKey' and all(
                row in json.loads(rbac)['data'].get('policy.csv', '').splitlines() for row in RULES):
            print('Scoped Argo read account reconciled; existing policies retained')
            return
        time.sleep(2)
    raise RuntimeError('Argo operator did not reconcile the portal read account')


if __name__ == '__main__': main()
