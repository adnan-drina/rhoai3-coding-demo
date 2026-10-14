"""Resume initial SonarQube password rotation without losing its credential."""
import base64
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://sonarqube.sonarqube.svc:9000'
PHASE = 'rhoai3.redhat.com/password-bootstrap'


def oc(*args, data=None):
    result = subprocess.run(['oc', *args], input=None if data is None else json.dumps(data),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
    if result.returncode:
        if '(NotFound)' in result.stderr: return None
        raise RuntimeError('SonarQube credential storage failed')
    return json.loads(result.stdout)


def request(path, password, data=None):
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    body = None if data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, body, {'Authorization': 'Basic ' + auth})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def valid(password):
    code, body = request('/api/authentication/validate', password)
    if code == 401: return False
    if code != 200: raise RuntimeError('SonarQube authentication probe HTTP %s' % code)
    result = json.loads(body)
    if type(result.get('valid')) is not bool:
        raise RuntimeError('SonarQube authentication probe has no boolean result')
    return result['valid']


def ensure_admin():
    row = oc('get', 'secret', 'sonarqube-admin', '-n', 'sonarqube', '-o', 'json')
    if row is None:
        # The random suffix supplies entropy; the prefix guarantees all four
        # character classes required by the selected SonarQube API.
        password = 'Aa1!' + secrets.token_urlsafe(24)
        row = oc('create', '-f', '-', '-o', 'json', data={
            'apiVersion': 'v1', 'kind': 'Secret',
            'metadata': {'name': 'sonarqube-admin', 'namespace': 'sonarqube',
                         'annotations': {PHASE: 'pending'}},
            'stringData': {'username': 'admin', 'password': password}})
        if row is None: raise RuntimeError('SonarQube credential was not persisted')
    password = base64.b64decode(row['data']['password']).decode()
    if not password: raise RuntimeError('SonarQube admin credential is empty')
    if not valid(password):
        if row.get('metadata', {}).get('annotations', {}).get(PHASE) != 'pending':
            raise RuntimeError('Stored SonarQube credential does not authenticate; preserve and reconcile it')
        if not valid('admin'):
            raise RuntimeError('Default and pending credentials both fail; preserve and reconcile them')
        code, unused = request('/api/users/change_password', 'admin', {
            'login': 'admin', 'previousPassword': 'admin', 'password': password})
        if code != 204:
            raise RuntimeError('SonarQube password rotation HTTP %s; pending credential retained' % code)
        if not valid(password): raise RuntimeError('Rotated SonarQube credential could not be verified')
    oc('patch', 'secret', 'sonarqube-admin', '-n', 'sonarqube', '--type=merge',
       '--patch-file=/dev/stdin', '-o', 'json', data={'metadata': {'annotations': {PHASE: 'ready'}}})
    return password


if __name__ == '__main__':
    try:
        # Captured by the Job shell, never echoed in the official Job log.
        print(ensure_admin())
    except Exception as error:
        print('ERROR: SonarQube admin bootstrap: %s' % type(error).__name__, file=sys.stderr)
        if isinstance(error, RuntimeError): print(str(error), file=sys.stderr)
        sys.exit(1)
