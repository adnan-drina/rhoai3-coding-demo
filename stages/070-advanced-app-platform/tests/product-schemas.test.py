#!/usr/bin/env python3
"""Validate configured fields against captured official schemas; no cluster writes."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'
FIXTURES = Path(__file__).with_name('fixtures')


class ProductSchemas(unittest.TestCase):
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
