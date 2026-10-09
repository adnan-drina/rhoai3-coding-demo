#!/usr/bin/env python3
"""Owned standalone Hermes setup using the established native agent lifecycle."""
import argparse
import json
import os
from pathlib import Path
import importlib.util

_source = importlib.util.spec_from_file_location('agent_setup', Path(__file__).with_name('setup-opencode.py'))
shared = importlib.util.module_from_spec(_source); _source.loader.exec_module(shared)
ROOT = shared.ROOT
NAME, WORKSPACE = 'hermes', 'ai-agents'
PROVIDER, SUBSCRIPTION = 'hermes-maas-qwen38', 'hermes-private-qwen38'
MODEL = shared.MODEL
MODEL_PROVIDER = 'qwen38'
PYTHON = '/opt/hermes-venv/bin/python3.11'
INPUTS = Path(__file__).with_name('hermes')
DIGEST = json.loads((INPUTS/'template.json').read_text())['image'].split('@',1)[1]

class Setup(shared.Setup):
    name, workspace, provider, subscription, model, image_digest = NAME, WORKSPACE, PROVIDER, SUBSCRIPTION, MODEL, DIGEST
    inputs = INPUTS
    helper_path = Path(__file__)
    image_tag = 'hermes-runtime-api:0.20.5-api'
    config_source, config_destination = 'config.yaml', 'state/hermes/config.yaml'
    listener_filename = 'server-key'
    # Both agents will use the reviewed shared canonical policy, before live setup.
    policy_path = Path(__file__).with_name('runtime')/'global-policy.yaml'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--persona-home',default=os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'),required=not os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'))
    parser.add_argument('--persona-kubeconfig',default=os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'),required=not os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'))
    parser.add_argument('--state-dir',default='/private/tmp/060-hermes-state')
    parser.add_argument('--expected-policy-hash')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();Setup(args).run()

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('[FAIL] '+(str(error) if isinstance(error,RuntimeError) else 'Bounded Hermes setup failed; inspect the private recovery journal'))
        raise SystemExit(1)
