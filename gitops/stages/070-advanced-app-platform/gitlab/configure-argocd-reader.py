"""Check the Developer Hub read account Stage 010 declares on the Argo CD instance; initialize enrollment parameters.

The account (spec.localUsers rhdh) and its rhdh-reader rules live in gitops/bootstrap/overlays/demo/argocd-instance.yaml,
so a Stage 010 apply can no longer drop rules this hook used to add."""
import json
import subprocess
import time

RULES = ['p, role:rhdh-reader, applications, get, rhoai-demo/*, allow',
         'p, role:rhdh-reader, applications, get, runtime-projects/*, allow',
         'p, role:rhdh-reader, applications, get, platform-projects/*, allow',
         'g, rhdh, role:rhdh-reader']


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
    for _ in range(60):
        account = subprocess.check_output(['oc', 'get', 'configmap', 'argocd-cm',
            '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True)
        rbac = subprocess.check_output(['oc', 'get', 'configmap', 'argocd-rbac-cm',
            '-n', 'openshift-gitops', '-o', 'json'], universal_newlines=True)
        if 'apiKey' in (json.loads(account)['data'].get('accounts.rhdh') or '') and all(
                row in json.loads(rbac)['data'].get('policy.csv', '').splitlines() for row in RULES):
            print('Developer Hub Argo CD read account and rules present')
            return
        time.sleep(2)
    raise RuntimeError('Argo CD lacks the rhdh local user or rhdh-reader rules; redeploy Stage 010 (argocd-instance.yaml)')


if __name__ == '__main__': main()
