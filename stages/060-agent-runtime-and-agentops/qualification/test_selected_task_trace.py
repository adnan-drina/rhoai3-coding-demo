"""Offline proof of selected-observation privacy and exact native event scope."""
import copy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

STAGE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('selected_task_trace',STAGE/'selected_task_trace.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
BINDING=dict(experiment_id='7',source_revision='a'*40,image_digest='sha256:'+'b'*64,
             sandbox_id='sandbox-owned',provider_id='provider-owned',session_id='session-owned',
             model=t.MODEL,subscription='hermes-private-qwen38')


class PrivacyTest(unittest.TestCase):
    def test_binding_rejects_unreviewed_content_or_model(self):
        self.assertEqual(t.binding_attributes('hermes',BINDING)['capture.scope'],t.COVERAGE)
        for changed in (dict(BINDING,prompt='private source'),dict(BINDING,model='foreign'),dict(BINDING,source_revision='HEAD')):
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):t.binding_attributes('hermes',changed)

    def test_hermes_event_drops_payload_and_rejects_foreign_run(self):
        event=dict(event='tool.completed',run_id='run_owned',tool='terminal',error=False,
                   preview='private code',arguments={'command':'private command'},output='private output')
        result=t.safe_event('hermes','session-owned','run_owned',event)
        self.assertEqual(result,('tool.completed',{'tool':'terminal','run_id':'run_owned','session_id':'session-owned','error':False}))
        self.assertIsNone(t.safe_event('hermes','session-owned','foreign',event))
        self.assertIsNone(t.safe_event('hermes','session-owned','run_owned',dict(event,event='message.delta',delta='private output')))

    def test_opencode_event_drops_tool_input_output_and_rejects_foreign_session(self):
        event={'type':'message.part.updated','properties':{'part':{'sessionID':'session-owned','type':'tool','tool':'bash',
               'state':{'status':'completed','input':{'command':'private command'},'output':'private output'}}}}
        self.assertEqual(t.safe_event('opencode','session-owned',None,event),('tool.completed',{'tool':'bash','session_id':'session-owned','status':'completed'}))
        self.assertIsNone(t.safe_event('opencode','foreign',None,event))

    def test_entire_stored_payload_scan_includes_server_added_fields(self):
        self.assertTrue(t.scan_payload({'info':{'request_preview':None},'data':{'request':None,'response':None}}))
        for value in ({'info':{'request_preview':'private source'}},{'server_metadata':{'Authorization':'Bearer private-token'}},
                      {'attributes':{'mlflow.spanInputs':'{"source":"private"}'}},{'events':[{'attributes':{'exception.message':'private failure'}}]},
                      {'server_metadata':{'unrecognized':'exact-private-password'}},{'server_metadata':{'unrecognized':'private\nquoted "value"'}}):
            with self.subTest(value=value),self.assertRaises(RuntimeError):t.scan_payload(value,('exact-private-password','private\nquoted "value"'))


class SpanLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.span=SimpleNamespace(trace_id='tr-owned',attributes={},events=[],status=None)
        self.span.set_attribute=lambda k,v:self.span.attributes.update({k:v})
        self.span.set_attributes=lambda values:self.span.attributes.update(values)
        self.span.set_status=lambda value:setattr(self.span,'status',value)
        self.span.add_event=lambda value:self.span.events.append(value)
        self.leaked=[]
        @contextmanager
        def start_span(**kwargs):
            self.span.attributes.update(kwargs['attributes'])
            try:yield self.span
            except BaseException as error:self.leaked.append(str(error));raise
        self.sdk=SimpleNamespace(start_span=start_span,flush_trace_async_logging=lambda:None)
        self.entity_module=SimpleNamespace(SpanEvent=lambda **kwargs:kwargs)

    def context(self):
        return patch.object(t,'configured_sdk',return_value=self.sdk),patch.dict(sys.modules,{'mlflow.entities':self.entity_module})

    def test_success_captures_real_tool_metadata_and_verified_hash_only(self):
        sdk,entities=self.context()
        with sdk,entities,t.selected_task_trace('hermes',BINDING) as trace:
            trace.bind_run('run_'+'a'*32)
            trace.observe(dict(event='tool.completed',run_id='run_'+'a'*32,tool='patch',error=False,preview='private source'))
            trace.complete(dict(passed=True,fixture_sha256='c'*64,output_tokens=10))
        self.assertEqual(self.span.status,'OK')
        self.assertTrue(t.scan_payload({'attributes':self.span.attributes,'events':self.span.events},('private source',)))

    def test_raw_exception_never_reaches_sdk_context(self):
        sdk,entities=self.context()
        with sdk,entities,self.assertRaisesRegex(RuntimeError,'no private error content'):
            with t.selected_task_trace('hermes',BINDING):raise ValueError('Bearer private-token and private code')
        self.assertFalse(self.leaked)
        self.assertEqual(self.span.status,'ERROR')
        self.assertTrue(t.scan_payload({'attributes':self.span.attributes}))

    def test_failed_tool_cannot_support_successful_task_receipt(self):
        trace=t.Observation('hermes',BINDING,self.span,self.entity_module.SpanEvent)
        trace.bind_run('run_'+'a'*32)
        trace.observe(dict(event='tool.completed',run_id=trace.run,tool='patch',error=True))
        with self.assertRaises(RuntimeError):trace.complete(dict(passed=True,fixture_sha256='c'*64))

    def test_fresh_readback_rejects_persisted_binding_outcome_type_or_event_drift(self):
        run='run_'+'a'*32;outcome=dict(passed=True,fixture_sha256='c'*64)
        attrs=t.binding_attributes('hermes',BINDING)
        attrs.update({'mlflow.spanType':'CLIENT','observed.run_id':run,**{'verified.'+k:v for k,v in outcome.items()}})
        root={'name':'agent.client.task','attributes':{k:json.dumps(v) for k,v in attrs.items()},
              'events':[{'name':'client.observed.tool.completed','attributes':json.dumps(dict(tool='patch',session_id=BINDING['session_id'],run_id=run,error=False))}]}
        receipt=dict(producer_pid=t.os.getpid()+1,workspace=t.WORKSPACE,capture_scope=t.COVERAGE,runtime='hermes',binding=BINDING,
                     experiment_id='7',trace_id='tr-owned',run_id=run,outcome=outcome,verified_task=True,export_flushed=True,observed_event_count=1)
        def read(payload):
            trace=SimpleNamespace(info=SimpleNamespace(trace_id='tr-owned',experiment_id='7'),to_dict=lambda:payload)
            sdk=SimpleNamespace(MlflowClient=lambda:SimpleNamespace(get_trace=lambda identifier:trace))
            with patch.object(t,'configured_sdk',return_value=sdk):return t.readback_trace(receipt)
        self.assertTrue(read({'data':{'spans':[root]}})['stored_payload_scan'])
        for key,value in (('mlflow.spanType','AGENT'),('observed.session_id','foreign'),('verified.fixture_sha256','d'*64),('verified.passed',False)):
            changed=copy.deepcopy(root);changed['attributes'][key]=json.dumps(value)
            with self.subTest(key=key),self.assertRaises(RuntimeError):read({'data':{'spans':[changed]}})
        changed=copy.deepcopy(root);changed['events'][0]['attributes']=json.dumps(dict(tool='patch',session_id=BINDING['session_id'],run_id=run,error=True))
        with self.assertRaises(RuntimeError):read({'data':{'spans':[changed]}})

    def test_plain_completion_is_not_a_verified_coding_observation(self):
        trace=t.Observation('hermes',BINDING,self.span,self.entity_module.SpanEvent)
        trace.bind_run('run_'+'a'*32)
        trace.observe(dict(event='run.completed',run_id=trace.run,output='private output'))
        with self.assertRaises(RuntimeError):trace.complete(dict(passed=True,fixture_sha256='c'*64))
        with self.assertRaises(RuntimeError):t.readback_trace(dict(producer_pid=t.os.getpid(),workspace=t.WORKSPACE,capture_scope=t.COVERAGE))


if __name__=='__main__':unittest.main()
