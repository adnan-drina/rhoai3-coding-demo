"""Link existing application identities to the base SSO without changing subjects."""
import base64
import json
import os
import subprocess
import urllib.parse
import urllib.request


def oc(*args):
    return json.loads(subprocess.check_output(['oc', *args, '-o', 'json'], universal_newlines=True))


def api(base, token, method, path, data=None):
    request = urllib.request.Request(base + path,
        None if data is None else json.dumps(data).encode(),
        {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def checked_base_issuer(oauth, host):
    providers = [p for p in oauth['spec']['identityProviders']
                 if p.get('name') == 'rhbk' and p.get('type') == 'OpenID']
    expected = 'https://' + host + '/realms/sso'
    if len(providers) != 1 or providers[0]['openID']['issuer'] != expected:
        raise ValueError('Base OpenShift SSO issuer does not match the existing Keycloak/sso realm')
    return expected


def identity_plan(base_users, application_users, openshift):
    """Username alone never authorizes linking an existing application account."""
    plans = []
    names = {u['username'] for u in application_users if not u.get('serviceAccountClientId')}
    names.update(('ai-admin', 'ai-developer'))
    for name in sorted(names):
        source = [u for u in base_users if u.get('username') == name and not u.get('serviceAccountClientId')]
        target = [u for u in application_users if u.get('username') == name]
        if len(source) != 1 or len(target) > 1 or not source[0].get('enabled'):
            raise ValueError('Missing, disabled or ambiguous base identity: ' + name)
        if target:
            user, identity, links = openshift(name, source[0]['id'], target[0]['id'])
            verified = (identity.get('user', {}).get('name') == name
                        and identity.get('user', {}).get('uid') == user['metadata']['uid'])
            old_links = [x for x in links if x['identityProvider'] == 'openshift']
            new_links = [x for x in links if x['identityProvider'] == 'base-sso']
            if not verified or (new_links and any(x['userId'] != source[0]['id'] for x in new_links)):
                raise ValueError('Conflicting base SSO identity: ' + name)
            if not new_links and (len(old_links) != 1 or old_links[0]['userId'] != user['metadata']['uid']):
                raise ValueError('Existing application identity has no verified OpenShift link: ' + name)
        plans.append((source[0], target[0] if target else None))
    return plans


def broker_client(host):
    origin = 'https://' + host
    return {'clientId': 'stage070-platform-broker', 'enabled': True, 'protocol': 'openid-connect',
        'publicClient': False, 'standardFlowEnabled': True, 'directAccessGrantsEnabled': False,
        'serviceAccountsEnabled': False, 'fullScopeAllowed': False,
        'redirectUris': [origin + '/realms/platform/broker/base-sso/endpoint'],
        'webOrigins': [origin], 'attributes': {'rhoai3.owner': 'stage070-base-sso'}}


def sonar_client(host):
    origin = 'https://' + host
    mappers = [{'name': 'sonarqube-' + attr, 'protocol': 'saml',
        'protocolMapper': 'saml-user-property-mapper',
        'config': {'user.attribute': prop, 'attribute.name': attr,
                   'attribute.nameformat': 'Basic'}}
        for attr, prop in [('login', 'username'), ('name', 'username'), ('email', 'email')]]
    return {'clientId': 'sonarqube', 'enabled': True, 'protocol': 'saml',
        'redirectUris': [origin + '/oauth2/callback/saml'], 'baseUrl': origin,
        'attributes': {'rhoai3.owner': 'stage070-base-sso', 'saml.server.signature': 'true',
            'saml.assertion.signature': 'true', 'saml.signature.algorithm': 'RSA_SHA256',
            'saml.client.signature': 'false', 'saml.force.post.binding': 'true',
            'saml_name_id_format': 'persistent', 'saml_force_name_id_format': 'true'},
        'protocolMappers': mappers, 'defaultClientScopes': []}


def main():
    host = oc('get', 'route', 'keycloak', '-n', 'keycloak')['spec']['host']
    base = 'https://' + host
    issuer = checked_base_issuer(oc('get', 'oauth.config.openshift.io', 'cluster'), host)
    admin = oc('get', 'secret', 'keycloak-initial-admin', '-n', 'keycloak')['data']
    credentials = {k: base64.b64decode(admin[k]).decode() for k in ('username', 'password')}
    request = urllib.request.Request(base + '/realms/master/protocol/openid-connect/token',
        urllib.parse.urlencode(dict(grant_type='password', client_id='admin-cli', **credentials)).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        token = json.load(response)['access_token']
    def realm(realm_name, method, path, data=None):
        return api(base, token, method, '/admin/realms/' + realm_name + '/' + path, data)
    def existing_link(name, subject, target):
        return (oc('get', 'users.user.openshift.io', name),
                oc('get', 'identities.user.openshift.io', 'rhbk:' + subject),
                realm('platform', 'GET', 'users/' + target + '/federated-identity'))
    base_users = realm('sso', 'GET', 'users?max=1000')
    app_users = realm('platform', 'GET', 'users?max=1000')
    if len(base_users) >= 1000 or len(app_users) >= 1000:
        raise ValueError('Identity inventory exceeds the reviewed bound')
    # Validate the entire linking plan before changing any user or client.
    plans = identity_plan(base_users, app_users, existing_link)
    providers = realm('platform', 'GET', 'identity-provider/instances')
    for provider in providers:
        if provider['alias'] == 'base-sso' and (
                provider.get('config', {}).get('issuer') != issuer or
                provider.get('config', {}).get('clientId') != 'stage070-platform-broker'):
            raise ValueError('Existing base-sso provider belongs to another identity integration')
    executions = realm('platform', 'GET', 'authentication/flows/browser/executions')
    redirectors = [e for e in executions if e.get('providerId') == 'identity-provider-redirector']
    if len(redirectors) != 1:
        raise ValueError('Expected the supported browser identity-provider redirector')
    domain = oc('get', 'ingresses.config.openshift.io', 'cluster')['spec']['domain']
    try:
        sonar_host = oc('get', 'route', 'sonarqube', '-n', 'sonarqube')['spec']['host']
    except subprocess.CalledProcessError as error:
        # Only absence permits the canonical host before the SonarQube wave.
        # API/permission failures must not silently select another callback.
        check = subprocess.run(['oc', 'get', 'route', 'sonarqube', '-n', 'sonarqube',
                                '--ignore-not-found', '-o', 'name'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if check.returncode or check.stdout.strip():
            raise error
        sonar_host = 'sonarqube-sonarqube.' + domain
    if not sonar_host.endswith('.' + domain):
        raise ValueError('SonarQube Route is outside the platform ingress domain')
    for client_name in ('stage070-platform-broker', 'sonarqube'):
        clients = realm('sso', 'GET', 'clients?clientId=' + client_name)
        if len(clients) > 1 or (clients and clients[0].get('attributes', {}).get('rhoai3.owner') != 'stage070-base-sso'):
            raise ValueError('Foreign or ambiguous base SSO client: ' + client_name)

    def ensure_client(desired):
        rows = realm('sso', 'GET', 'clients?clientId=' + desired['clientId'])
        if len(rows) > 1 or (rows and rows[0].get('attributes', {}).get('rhoai3.owner') != 'stage070-base-sso'):
            raise ValueError('Foreign or ambiguous base SSO client: ' + desired['clientId'])
        if rows:
            realm('sso', 'PUT', 'clients/' + rows[0]['id'], {**rows[0], **desired})
        else:
            realm('sso', 'POST', 'clients', desired)
            rows = realm('sso', 'GET', 'clients?clientId=' + desired['clientId'])
        return rows[0]['id']
    client = ensure_client(broker_client(host))
    secret = realm('sso', 'GET', 'clients/' + client + '/client-secret')['value']
    # These are public endpoints. No master credential is given to applications.
    idp = {'alias': 'base-sso', 'displayName': 'Platform SSO', 'providerId': 'oidc',
        'enabled': True, 'trustEmail': False, 'storeToken': False,
        'firstBrokerLoginFlowAlias': 'first broker login', 'config': {
            'clientId': 'stage070-platform-broker', 'clientSecret': secret,
            'authorizationUrl': issuer + '/protocol/openid-connect/auth',
            'tokenUrl': issuer + '/protocol/openid-connect/token',
            'userInfoUrl': issuer + '/protocol/openid-connect/userinfo',
            'logoutUrl': issuer + '/protocol/openid-connect/logout',
            'jwksUrl': issuer + '/protocol/openid-connect/certs', 'issuer': issuer,
            'validateSignature': 'true', 'useJwksUrl': 'true',
            'syncMode': 'IMPORT', 'defaultScope': 'openid profile email'}}
    if any(x['alias'] == 'base-sso' for x in providers):
        realm('platform', 'PUT', 'identity-provider/instances/base-sso', idp)
    else:
        realm('platform', 'POST', 'identity-provider/instances', idp)
    for source, target in plans:
        if target is None:
            realm('platform', 'POST', 'users', {k: source[k] for k in
                ('username', 'enabled', 'firstName', 'lastName', 'email', 'emailVerified') if k in source})
            target = realm('platform', 'GET', 'users?username=' + urllib.parse.quote(source['username']) + '&exact=true')[0]
        links = realm('platform', 'GET', 'users/' + target['id'] + '/federated-identity')
        if not any(x['identityProvider'] == 'base-sso' for x in links):
            realm('platform', 'POST', 'users/' + target['id'] + '/federated-identity/base-sso',
                  {'identityProvider': 'base-sso', 'userId': source['id'], 'userName': source['username']})
    execution = redirectors[0]
    if execution.get('authenticationConfig'):
        config = realm('platform', 'GET', 'authentication/config/' + execution['authenticationConfig'])
        config['config']['defaultProvider'] = 'base-sso'
        realm('platform', 'PUT', 'authentication/config/' + config['id'], config)
    else:
        realm('platform', 'POST', 'authentication/executions/' + execution['id'] + '/config',
              {'alias': 'stage070-base-sso', 'config': {'defaultProvider': 'base-sso'}})
    # Retain the old links for rollback, but stop offering the indirect login path.
    for provider in providers:
        if provider['alias'] == 'openshift':
            provider['enabled'] = False
            realm('platform', 'PUT', 'identity-provider/instances/openshift', provider)
    ensure_client(sonar_client(sonar_host))
    os.environ['SCM_IDENTITY_URL'] = base
    os.environ['SCM_ADMIN_TOKEN'] = token
    subprocess.run(['python3', '/scripts/configure-scm-identity.py'], check=True)
    print('Base SSO linked; application subjects, roles, credentials and base-platform clients preserved')


if __name__ == '__main__':
    main()
