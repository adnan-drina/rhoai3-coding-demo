"""Offline regression: separate retained agent scopes survive shared setup reuse."""
import importlib.util
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE))
spec=importlib.util.spec_from_file_location('hermes_setup',STAGE/'setup-hermes.py')
hermes=importlib.util.module_from_spec(spec);spec.loader.exec_module(hermes)
shared=hermes.shared

class AgentScope(unittest.TestCase):
    def probe(self,cls,other_scope=False):
        obj=cls.__new__(cls);expiry=(datetime.now(timezone.utc)+timedelta(days=20)).isoformat()
        obj.state={'key_id':'unit-id','key_tenant':'unit-tenant','key_expiry':expiry}
        obj.api='https://unit.invalid';obj.user_token='unit-not-a-credential'
        metadata={'id':'unit-id','name':obj.name+'-runtime-qwen38','username':'ai-admin','subscription':obj.subscription,'ephemeral':False,'status':'active','tenant':'unit-tenant','expirationDate':expiry}
        if other_scope:metadata['subscription']='personal-ai-admin'
        with patch.object(shared.checks,'http',return_value=(200,metadata)):
            obj.key_metadata()
    def test_existing_opencode_scope_still_valid(self):self.probe(shared.Setup)
    def test_hermes_own_scope_valid(self):self.probe(hermes.Setup)
    def test_hermes_refuses_broad_personal_key(self):
        with self.assertRaisesRegex(RuntimeError,'model subscription is not active'):self.probe(hermes.Setup,True)
    def test_opencode_refuses_broad_personal_key(self):
        with self.assertRaisesRegex(RuntimeError,'model subscription is not active'):self.probe(shared.Setup,True)

if __name__=='__main__':unittest.main()
