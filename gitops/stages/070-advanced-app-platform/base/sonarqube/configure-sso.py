"""Use SonarQube's supported SAML integration; retain local users and permissions."""
import base64
import json
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def oc(*args):
    return json.loads(subprocess.check_output(['oc', *args, '-o', 'json'], universal_newlines=True))


def configuration(issuer, sonar_url, metadata):
    if not issuer.startswith('https://') or not issuer.endswith('/realms/sso'):
        raise ValueError('Expected the existing HTTPS base SSO issuer')
    root = ET.fromstring(metadata)
    namespaces = {'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
                  'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    if root.attrib.get('entityID') != issuer:
        raise ValueError('SAML metadata belongs to another issuer')
    idp = root.find('md:IDPSSODescriptor', namespaces)
    if idp is None:
        raise ValueError('SSO metadata has no identity-provider descriptor')
    certificates = idp.findall('md:KeyDescriptor[@use="signing"]/ds:KeyInfo/ds:X509Data/ds:X509Certificate', namespaces)
    if not certificates or not certificates[0].text:
        raise ValueError('SSO metadata has no assertion-signing certificate')
    certificate = ''.join(certificates[0].text.split())
    base64.b64decode(certificate, validate=True)
    endpoints = idp.findall('md:SingleSignOnService', namespaces)
    if not any(e.get('Location') == issuer + '/protocol/saml' for e in endpoints):
        raise ValueError('SAML login endpoint is outside the base SSO issuer')
    return {'sonar.core.serverBaseURL': sonar_url,
        'sonar.auth.saml.applicationId': 'sonarqube',
        'sonar.auth.saml.providerName': 'Platform SSO',
        'sonar.auth.saml.providerId': issuer,
        'sonar.auth.saml.loginUrl': issuer + '/protocol/saml',
        'sonar.auth.saml.certificate.secured': certificate,
        'sonar.auth.saml.user.login': 'login', 'sonar.auth.saml.user.name': 'name',
        'sonar.auth.saml.user.email': 'email'}


def main():
    oauth = oc('get', 'oauth.config.openshift.io', 'cluster')
    providers = [p for p in oauth['spec']['identityProviders']
                 if p.get('name') == 'rhbk' and p.get('type') == 'OpenID']
    if len(providers) != 1:
        raise ValueError('Expected exactly one base OpenShift SSO provider')
    issuer = providers[0]['openID']['issuer']
    sonar_host = oc('get', 'route', 'sonarqube', '-n', 'sonarqube')['spec']['host']
    if not issuer.startswith('https://') or not issuer.endswith('/realms/sso'):
        raise ValueError('Unexpected base platform issuer')
    with urllib.request.urlopen(issuer + '/protocol/saml/descriptor', timeout=30) as response:
        settings = configuration(issuer, 'https://' + sonar_host, response.read())
    secret = oc('get', 'secret', 'sonarqube-admin', '-n', 'sonarqube')['data']
    auth = base64.b64encode(b'admin:' + base64.b64decode(secret['password'])).decode()
    for key, value in settings.items():
        request = urllib.request.Request('http://sonarqube.sonarqube.svc:9000/api/settings/set',
            urllib.parse.urlencode({'key': key, 'value': value}).encode(),
            {'Authorization': 'Basic ' + auth}, method='POST')
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 204:
                raise RuntimeError('SonarQube rejected an SSO setting')
    # Enable last, after the issuer, callback, attributes and signing certificate.
    request = urllib.request.Request('http://sonarqube.sonarqube.svc:9000/api/settings/set',
        urllib.parse.urlencode({'key': 'sonar.auth.saml.enabled', 'value': 'true'}).encode(),
        {'Authorization': 'Basic ' + auth}, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 204:
            raise RuntimeError('SonarQube rejected SAML enablement')
    print('SonarQube base SSO configured; local admin, tokens, groups and permissions retained')


if __name__ == '__main__':
    main()
