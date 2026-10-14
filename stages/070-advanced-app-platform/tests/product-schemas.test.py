#!/usr/bin/env python3
"""Validate configured fields against captured official schemas; no cluster writes."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform'
sys.path.insert(0, str(BASE / 'pipelines/gitlab'))
FIXTURES = Path(__file__).with_name('fixtures')


class ProductSchemas(unittest.TestCase):
    def test_controller_memory_policy_uses_the_openshift_422_schema(self):
        policy = yaml.safe_load((BASE / 'mta/controller-sizing/agentic-memory.yaml').read_text())
        schema = json.loads((FIXTURES / 'vpa-4.22-spec.schema.json').read_text())['schema']
        jsonschema.validate(policy['spec'], schema)
        self.assertEqual(policy['spec']['targetRef'], {
            'apiVersion': 'apps/v1', 'kind': 'Deployment', 'name': 'agentic-controller'})
        self.assertEqual(policy['metadata']['namespace'], 'openshift-mta')
        manager = next(c for c in policy['spec']['resourcePolicy']['containerPolicies'] if c['containerName'] == 'manager')
        self.assertEqual(manager['controlledResources'], ['memory'])
        self.assertEqual(manager['controlledValues'], 'RequestsAndLimits')
        self.assertEqual(manager['minAllowed'], {'memory': '256Mi'})
        self.assertEqual(manager['maxAllowed'], {'memory': '512Mi'})
        # Keep the single-replica exception local. Other workloads, including
        # stopped models, are not selected by this policy.
        self.assertEqual(policy['spec']['updatePolicy'], {'minReplicas': 1, 'updateMode': 'Recreate'})
        controller = yaml.safe_load((BASE / 'mta/controller-sizing/controller.yaml').read_text())
        self.assertEqual(controller['spec']['minReplicas'], 2)

    def test_template_gitlab_inputs_match_installed_action_schemas(self):
        # Captured from official factory.schema objects in the installed RHDH
        # 1.10.5 gitlab-dynamic 0.11.4 module, 2026-10-14; no handlers invoked.
        captured = json.loads((FIXTURES / 'rhdh-1.10.5-gitlab-actions.json').read_text())
        schemas = {a['id']: a['schema'] for a in captured['actions']}
        for name in ('agentic-quarkus-scaffold', 'app-migration'):
            template = yaml.safe_load((BASE / ('rhdh/templates/' + name + '/template.yaml')).read_text())
            for step in template['spec']['steps']:
                if step['action'] not in schemas:
                    continue
                with self.subTest(template=name, action=step['action']):
                    inputs = copy.deepcopy(step['input'])
                    if 'projectId' in inputs:
                        inputs['projectId'] = 42  # the template's explicit int filter
                    errors = list(jsonschema.Draft7Validator(schemas[step['action']]['input']).iter_errors(inputs))
                    self.assertFalse(errors, [e.message for e in errors])
                    if step['action'] == 'publish:gitlab':
                        self.assertEqual(inputs['settings']['visibility'], 'private')
                        self.assertEqual(inputs['defaultBranch'], 'main')
                        self.assertIn('rhoai3-scaffolded', inputs['settings']['topics'])
                        # Enrollment consumes only native, declared outputs.
                        for field in ('projectId', 'commitHash', 'remoteUrl'):
                            self.assertIn(field, schemas[step['action']]['output']['properties'])

    def test_tackle_parameters_are_implemented_by_the_downstream_operator(self):
        spec = yaml.safe_load((BASE / 'mta/mta-instance/tackle.yaml').read_text())['spec']
        defaults = json.loads((FIXTURES / 'mta-tackle-8.3-defaults.json').read_text())
        # The actual CRD preserves unknown fields. Check the operand's declared
        # defaults instead of inventing a typed schema that would accept typos.
        self.assertLessEqual(set(spec) | {'kai_llm_baseurl'}, set(defaults['parameter_names']))
        self.assertNotIn('rwo_storage_class', spec)

    def test_mta_gateway_matches_the_actual_83_operator(self):
        documents = list(yaml.safe_load_all((BASE / 'mta/jobs/configure-ai.yaml').read_text()))
        gateway = next(d for d in documents if d['kind'] == 'Gateway')
        schema = json.loads((FIXTURES / 'mta-gateway-8.3.schema.json').read_text())['schema']
        jsonschema.validate(gateway['spec'], schema)
        invalid = copy.deepcopy(gateway['spec']); del invalid['credentialRef']
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(invalid, schema)

    def test_tas_configured_fields_use_the_actual_15_spelling_and_types(self):
        secure = yaml.safe_load((BASE / 'pipelines/signing/securesign.yaml').read_text())
        schema = json.loads((FIXTURES / 'tas-securesign-1.5.schema.json').read_text())['schema']
        jsonschema.validate(secure['spec'], schema)
        invalid = copy.deepcopy(secure['spec'])
        invalid['fulcio']['config']['OIDCIssuers'] = invalid['fulcio']['config'].pop('oidcIssuers')
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(invalid, schema)

    def test_both_migration_protocols_render_valid_devfiles(self):
        path = BASE / 'rhdh/templates/app-migration/app-migration-template.test.py'
        spec = importlib.util.spec_from_file_location('migration_template', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        schema = json.loads((FIXTURES / 'devfile-2.2.2.schema.json').read_text())
        for protocol in ('serial-loop/v1', 'outcome-board/v2'):
            jsonschema.validate(yaml.safe_load(module.render('devfile.yaml', protocol)), schema)


if __name__ == '__main__': unittest.main()
