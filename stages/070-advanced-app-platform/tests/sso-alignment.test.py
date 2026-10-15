#!/usr/bin/env python3
"""Account preservation, conflicting-subject refusals and signed SAML configuration."""
import base64
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform'
sys.path.insert(0, str(BASE / 'pipelines/gitlab'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


identity = load('base_sso', 'identity/jobs/configure-base-sso.py')
sonar = load('sonar_sso', 'sonarqube/configure-sso.py')
signing = load('signing_sso', 'pipelines/signing/configure-signing.py')


class IdentityPreservation(unittest.TestCase):
    def setUp(self):
        self.base = [{'username': n, 'id': 'base-' + n, 'enabled': True, 'emailVerified': False}
                     for n in ('ai-admin', 'ai-developer')]
        self.app = [{'username': n, 'id': 'existing-' + n, 'enabled': True}
                    for n in ('ai-admin', 'ai-developer')]
        self.link = 'source-ai-admin'
        self.direct = []

    def openshift(self, name, subject, target):
        return ({'metadata': {'uid': 'source-' + name}},
                {'user': {'name': name, 'uid': 'source-' + name}},
                [{'identityProvider': 'openshift', 'userId': 'source-' + name}] + self.direct)

    def test_existing_subjects_are_preserved_without_changing_profiles(self):
        before = copy.deepcopy((self.base, self.app))
        plans = identity.identity_plan(self.base, self.app, self.openshift)
        self.assertEqual([p[1]['id'] for p in plans], ['existing-ai-admin', 'existing-ai-developer'])
        self.assertEqual((self.base, self.app), before)
        # A subject-bound login does not require inventing email verification.
        self.assertFalse(any(p[0]['emailVerified'] for p in plans))

    def test_unbound_existing_user_is_refused(self):
        def unbound(*args):
            u, i, links = self.openshift(*args)
            return u, i, []
        with self.assertRaisesRegex(ValueError, 'no verified OpenShift link'):
            identity.identity_plan(self.base, self.app, unbound)

    def test_stale_openshift_subject_is_refused(self):
        def stale(*args):
            u, i, links = self.openshift(*args)
            links[0]['userId'] = 'another-user'
            return u, i, links
        with self.assertRaisesRegex(ValueError, 'no verified OpenShift link'):
            identity.identity_plan(self.base, self.app, stale)

    def test_base_identity_points_at_another_openshift_user(self):
        def foreign(*args):
            u, i, links = self.openshift(*args)
            i['user']['uid'] = 'foreign'
            return u, i, links
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            identity.identity_plan(self.base, self.app, foreign)

    def test_conflicting_direct_subject_is_refused(self):
        self.direct = [{'identityProvider': 'base-sso', 'userId': 'foreign'}]
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            identity.identity_plan(self.base, self.app, self.openshift)

    def test_bound_rerun_does_not_require_recreating_old_links(self):
        def bound(name, subject, target):
            u, i, links = self.openshift(name, subject, target)
            return u, i, [{'identityProvider': 'base-sso', 'userId': subject}]
        plans = identity.identity_plan(self.base, self.app, bound)
        self.assertEqual(plans[0][1]['id'], 'existing-ai-admin')

    def test_duplicate_or_disabled_base_user_is_refused(self):
        with self.assertRaises(ValueError):
            identity.identity_plan(self.base + [self.base[0]], self.app, self.openshift)
        self.base[0]['enabled'] = False
        with self.assertRaises(ValueError):
            identity.identity_plan(self.base, self.app, self.openshift)

    def test_foreign_issuer_is_refused(self):
        oauth = {'spec': {'identityProviders': [{'name': 'rhbk', 'type': 'OpenID',
                    'openID': {'issuer': 'https://sso.example/realms/sso'}}]}}
        self.assertEqual(identity.checked_base_issuer(oauth, 'sso.example'), 'https://sso.example/realms/sso')
        oauth['spec']['identityProviders'][0]['openID']['issuer'] = 'https://other.example/realms/sso'
        with self.assertRaises(ValueError):
            identity.checked_base_issuer(oauth, 'sso.example')

    def test_broker_has_no_base_realm_management_authority(self):
        client = identity.broker_client('sso.example')
        self.assertFalse(client['fullScopeAllowed'])
        self.assertFalse(client['serviceAccountsEnabled'])
        self.assertFalse(client['directAccessGrantsEnabled'])
        self.assertEqual(client['redirectUris'], ['https://sso.example/realms/platform/broker/base-sso/endpoint'])

    def test_broker_logout_allows_only_its_exact_response_endpoint(self):
        client = identity.broker_client('sso.example')
        self.assertEqual(client['attributes'].get('post.logout.redirect.uris'),
                         'https://sso.example/realms/platform/broker/base-sso/endpoint/logout_response')
        self.assertEqual(client['redirectUris'],
                         ['https://sso.example/realms/platform/broker/base-sso/endpoint'])
        self.assertNotIn('*', str(client))
        self.assertNotEqual(client['attributes']['post.logout.redirect.uris'], '+')

    def test_cluster_identity_configuration_is_read_only(self):
        resources = list(yaml.safe_load_all((BASE / 'identity/jobs/configure-platform-identity.yaml').read_text()))
        role = next(r for r in resources if r['kind'] == 'ClusterRole')
        self.assertTrue(all(rule['verbs'] == ['get'] for rule in role['rules']))
        self.assertNotIn('oauthclients', str(role))
        job = next(r for r in resources if r['kind'] == 'Job')
        self.assertEqual(job['spec']['template']['spec']['containers'][0]['command'],
                         ['python3', '/scripts/configure-base-sso.py'])


class SignedSAML(unittest.TestCase):
    issuer = 'https://sso.example/realms/sso'

    def metadata(self, issuer=None, certificate='Y2VydGlmaWNhdGU='):
        return '''<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="%s">
          <IDPSSODescriptor><KeyDescriptor use="signing"><KeyInfo xmlns="http://www.w3.org/2000/09/xmldsig#">
          <X509Data><X509Certificate>%s</X509Certificate></X509Data></KeyInfo></KeyDescriptor>
          <SingleSignOnService Location="%s/protocol/saml"/></IDPSSODescriptor></EntityDescriptor>''' % (
            issuer or self.issuer, certificate, issuer or self.issuer)

    def test_correct_issuer_and_certificate_and_no_group_reset(self):
        config = sonar.configuration(self.issuer, 'https://sonar.example', self.metadata())
        self.assertEqual(config['sonar.auth.saml.providerId'], self.issuer)
        self.assertEqual(config['sonar.auth.saml.certificate.secured'], 'Y2VydGlmaWNhdGU=')
        self.assertNotIn('sonar.auth.saml.group.name', config)
        self.assertFalse(any('password' in k or 'permission' in k for k in config))

    def test_wrong_issuer_missing_or_malformed_certificate_refused(self):
        for metadata in [self.metadata('https://foreign.example/realms/sso'),
                         self.metadata(certificate=''), self.metadata(certificate='not-a-certificate')]:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                sonar.configuration(self.issuer, 'https://sonar.example', metadata)

    def test_foreign_login_endpoint_refused(self):
        metadata = self.metadata().replace(self.issuer + '/protocol/saml', 'https://foreign.example/login')
        with self.assertRaisesRegex(ValueError, 'login endpoint'):
            sonar.configuration(self.issuer, 'https://sonar.example', metadata)

    def test_keycloak_signs_assertions_and_uses_exact_callback(self):
        client = identity.sonar_client('sonar.example')
        self.assertEqual(client['redirectUris'], ['https://sonar.example/oauth2/callback/saml'])
        self.assertEqual(client['attributes']['saml.assertion.signature'], 'true')
        self.assertEqual(client['attributes']['saml.server.signature'], 'true')
        self.assertEqual(client['attributes']['saml.signature.algorithm'], 'RSA_SHA256')
        self.assertEqual(client['defaultClientScopes'], [])

    def test_sonar_does_not_receive_keycloak_administrator_credentials(self):
        resources = list(yaml.safe_load_all((BASE / 'sonarqube/configure-sonarqube.yaml').read_text()))
        role = next(r for r in resources if r['kind'] == 'ClusterRole')
        self.assertEqual(role['rules'], [{'apiGroups': ['config.openshift.io'], 'resources': ['oauths'],
                                        'resourceNames': ['cluster'], 'verbs': ['get']}])
        self.assertNotIn('keycloak-initial-admin', (BASE / 'sonarqube/configure-sso.py').read_text())


class ReconciliationSafety(unittest.TestCase):
    def test_runtime_secret_cannot_overwrite_ignored_data_through_string_data(self):
        secret = yaml.safe_load((BASE / 'rhdh/rhdh-instance/rhdh-secrets.yaml').read_text())
        application = yaml.safe_load((ROOT / 'gitops/applications/070-rhdh.yaml').read_text())
        self.assertNotIn('stringData', secret)
        self.assertEqual(base64.b64decode(secret['data']['SESSION_SECRET']).decode(), 'PLACEHOLDER_WILL_BE_PATCHED')
        self.assertEqual(base64.b64decode(secret['data']['RHDH_OIDC_CLIENT_SECRET']).decode(), 'PLACEHOLDER_WILL_BE_PATCHED')
        self.assertIn('RespectIgnoreDifferences=true', application['spec']['syncPolicy']['syncOptions'])
        ignore = next(r for r in application['spec']['ignoreDifferences']
                      if r.get('name') == 'rhdh-secrets' and r.get('namespace') == 'rhdh')
        self.assertIn('/data', ignore['jsonPointers'])

    def test_signer_uses_exact_loopback_paths_with_pkce_and_no_password_grant(self):
        client = signing.client_configuration()
        self.assertEqual(client['redirectUris'], ['http://localhost/auth/callback', 'http://localhost:80/auth/callback'])
        self.assertTrue(client['publicClient'])
        self.assertFalse(client['serviceAccountsEnabled'])
        self.assertFalse(client['directAccessGrantsEnabled'])
        self.assertEqual(client['attributes']['pkce.code.challenge.method'], 'S256')
        self.assertFalse(any('*' in uri for uri in client['redirectUris']))


if __name__ == '__main__':
    unittest.main()
