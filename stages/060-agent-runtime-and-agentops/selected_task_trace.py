"""Explicit MLflow 3.14 client observations of a selected native agent task.

No automatic instrumentation, inference, experiment creation or permissions.
The caller owns authenticated native transport, new session/run and verification.
"""
from contextlib import contextmanager
import json
import os
import re
import time
from urllib.parse import urlparse

SDK_VERSION = '3.14.0'
WORKSPACE = 'ai-agents'
EXPERIMENT = 'agent-runtime-traces'
MODEL = 'publishers/internal-models/models/qwen3-8-27b-int4'
COVERAGE = 'native-api-client-observation; no native internal spans'
FIELDS = {'experiment_id','source_revision','image_digest','sandbox_id','provider_id','session_id','model','subscription'}
TOOLS = {'hermes': {'write_file','patch','terminal','read_file','search_files'},
         'opencode': {'edit','write','apply_patch','bash','read','glob','grep','list'}}
CONTENT_FIELDS = {'input','inputs','spaninputs','output','outputs','spanoutputs','request','response',
                  'requestpreview','responsepreview','prompt','message','detail','content','arguments','command','preview','delta',
                  'authorization','headers','apikey','password','token','stacktrace','errormessage','exception'}


def need(value, message):
    if not value: raise RuntimeError(message)


def binding_attributes(runtime, binding):
    need(runtime in TOOLS and set(binding) == FIELDS, 'Exact selected task trace binding required')
    need(binding['model'] == MODEL and binding['subscription'] == runtime+'-private-qwen38', 'Selected model/subscription differs')
    need(re.fullmatch(r'[0-9a-f]{40}',binding['source_revision']) and
         re.fullmatch(r'sha256:[0-9a-f]{64}',binding['image_digest']) and
         re.fullmatch(r'[0-9]+',binding['experiment_id']), 'Reviewed source/image/experiment identity differs')
    for field in ('sandbox_id','provider_id','session_id'):
        need(isinstance(binding[field],str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',binding[field]), 'Native trace binding ID differs')
    return {'capture.scope':COVERAGE,'runtime':runtime,'workspace':WORKSPACE,
            **{'observed.'+k:v for k,v in binding.items() if k != 'experiment_id'},
            'maas.correlation':'subscription/model/time window; no per-request ID join'}


def safe_event(runtime, session, run, event):
    """Project real native events; never copy arbitrary input fields."""
    if runtime == 'hermes':
        if not run or event.get('run_id') != run: return None
        kind = event.get('event')
        if kind in ('tool.started','tool.completed'):
            tool = event.get('tool');need(tool in TOOLS[runtime], 'Unreviewed observed tool name')
            attrs = {'tool':tool,'run_id':run,'session_id':session}
            if kind == 'tool.completed':
                need(type(event.get('error')) is bool, 'Native tool outcome unavailable')
                attrs['error'] = event['error']
            return kind,attrs
        if kind in ('run.completed','run.cancelled','run.failed'):
            return kind,{'run_id':run,'session_id':session}
    else:
        kind = event.get('type');properties = event.get('properties',{})
        part = properties.get('part',{})
        if kind != 'message.part.updated' or part.get('sessionID') != session or part.get('type') != 'tool': return None
        tool = part.get('tool');need(tool in TOOLS[runtime], 'Unreviewed observed tool name')
        status = part.get('state',{}).get('status');need(status in ('pending','running','completed','error'), 'Native tool state differs')
        return 'tool.'+status,{'tool':tool,'session_id':session,'status':status}
    return None


def scan_payload(payload, forbidden_values=()):
    """Scan the entire serialized stored trace, including server-added metadata."""
    raw = json.dumps(payload,sort_keys=True)
    need(len(raw.encode()) <= 262144, 'Stored selected trace exceeds bounded size')
    need(not any(value and value in raw for value in forbidden_values), 'Forbidden private value in stored trace')
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                normalized = re.sub(r'[^a-z]','',key.rsplit('.',1)[-1].lower())
                if normalized in CONTENT_FIELDS:
                    need(item in (None,'',{},[],'null','{}','[]'), 'Unexpected captured content field in stored trace')
                visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,str):
            need(not any(secret and secret in value for secret in forbidden_values), 'Forbidden private value in stored trace')
            need(not re.search(r'(?i)(?:bearer|basic)\s+\S+|openshell:resolve:env:|\bsk-[A-Za-z0-9_-]{10,}',value), 'Credential-shaped value in stored trace')
    visit(payload)
    return True


def configured_sdk(experiment_id):
    import mlflow
    need(mlflow.__version__ == SDK_VERSION, 'Pinned external MLflow SDK required')
    uri = urlparse(os.environ.get('MLFLOW_TRACKING_URI',''))
    need(uri.scheme == 'https' and uri.hostname and not uri.username and not uri.password and
         uri.path.rstrip('/') in ('','/mlflow') and not uri.query and not uri.fragment and
         os.environ.get('MLFLOW_TRACKING_AUTH') == 'kubernetes-namespaced' and
         os.environ.get('MLFLOW_WORKSPACE') == WORKSPACE and
         os.environ.get('MLFLOW_TRACKING_INSECURE_TLS','false').lower() not in ('true','1'),
         'Verified native TLS/plugin/workspace configuration required')
    try:
        mlflow.set_workspace(WORKSPACE)
        need(mlflow.get_workspace(WORKSPACE).name == WORKSPACE, 'Exact MLflow workspace unavailable')
        experiment = mlflow.get_experiment(experiment_id)
        need(experiment and experiment.experiment_id == experiment_id and experiment.name == EXPERIMENT and
             experiment.lifecycle_stage == 'active', 'Exact active authorized trace experiment required')
        mlflow.set_experiment(experiment_id=experiment_id)
    except Exception:
        raise RuntimeError('MLflow workspace/experiment authorization preflight failed') from None
    return mlflow


class Observation:
    def __init__(self, runtime, binding, span, event_type):
        self.runtime,self.binding,self.span,self.event_type = runtime,binding,span,event_type
        self.run = None;self.events = 0;self.tool_completed = 0;self.completed = False
        self.receipt = {'trace_id':span.trace_id,'experiment_id':binding['experiment_id'],'workspace':WORKSPACE,
                        'producer_pid':os.getpid(),'runtime':runtime,'capture_scope':COVERAGE,'binding':dict(binding)}

    def bind_run(self, run):
        need(self.runtime == 'hermes' and self.run is None and re.fullmatch(r'run_[0-9a-f]{32}',run), 'Exact newly accepted native run required')
        self.run = run;self.receipt['run_id'] = run;self.span.set_attribute('observed.run_id',run)

    def observe(self, event):
        projected = safe_event(self.runtime,self.binding['session_id'],self.run,event)
        if projected is None:return
        need(self.events < 64, 'Bounded observed event count exceeded')
        name,attributes = projected
        self.span.add_event(self.event_type(name='client.observed.'+name,timestamp=time.time_ns(),attributes=attributes))
        self.events += 1
        if name == 'tool.completed' and attributes.get('error',False) is False:self.tool_completed += 1

    def complete(self, outcome):
        need(set(outcome) <= {'passed','fixture_sha256','input_tokens','output_tokens','total_tokens'} and
             outcome.get('passed') is True and re.fullmatch(r'[0-9a-f]{64}',outcome.get('fixture_sha256','')) and
             self.tool_completed > 0 and not self.completed, 'Exact independently verified observed task outcome required')
        for key,value in outcome.items():
            if key.endswith('_tokens'):need(type(value) is int and 0 <= value <= 1000000, 'Bounded native usage count differs')
        self.span.set_attributes({'verified.'+key:value for key,value in outcome.items()})
        self.span.set_attribute('observed.event_count',self.events);self.span.set_status('OK')
        self.completed = True;self.receipt['outcome'] = dict(outcome)


@contextmanager
def selected_task_trace(runtime, binding):
    attributes = binding_attributes(runtime,binding)
    mlflow = configured_sdk(binding['experiment_id'])
    from mlflow.entities import SpanEvent
    failed = False
    with mlflow.start_span(name='agent.client.task',span_type='CLIENT',attributes=attributes) as span:
        observation = Observation(runtime,binding,span,SpanEvent)
        try:
            yield observation
            need(observation.completed, 'Selected task outcome was not verified')
        except BaseException:
            # Catch before MLflow's context manager can record raw exception text.
            span.set_attribute('verified.passed',False);span.set_status('ERROR');failed = True
    try:mlflow.flush_trace_async_logging()
    except Exception:raise RuntimeError('Selected trace export did not flush') from None
    observation.receipt.update(export_flushed=True,verified_task=observation.completed and not failed,observed_event_count=observation.events)
    if failed:raise RuntimeError('Selected observed task failed; no private error content captured') from None


def readback_trace(receipt, forbidden_values=()):
    """Call only in a fresh process; a same-process trace cache proves no storage."""
    need(receipt['producer_pid'] != os.getpid() and receipt['workspace'] == WORKSPACE and
         receipt['capture_scope'] == COVERAGE, 'Fresh exact-workspace trace readback required')
    mlflow = configured_sdk(receipt['experiment_id'])
    try:trace = mlflow.MlflowClient().get_trace(receipt['trace_id'])
    except Exception:raise RuntimeError('Stored exact trace retrieval failed') from None
    need(trace and trace.info.trace_id == receipt['trace_id'] and trace.info.experiment_id == receipt['experiment_id'], 'Stored trace identity/location differs')
    payload = trace.to_dict();scan_payload(payload,forbidden_values)
    spans = payload.get('data',{}).get('spans',[])
    need(len(spans) == 1 and spans[0].get('name') == 'agent.client.task' and spans[0].get('events'), 'Stored real client observations unavailable')
    attributes = spans[0].get('attributes',{})
    def decoded(value):
        if isinstance(value,str):
            try:return json.loads(value)
            except ValueError:pass
        return value
    expected = binding_attributes(receipt['runtime'],receipt['binding'])
    need(all(decoded(attributes.get(key)) == value for key,value in expected.items()) and
         decoded(attributes.get('mlflow.spanType')) == 'CLIENT', 'Stored trace observation binding differs')
    if receipt['runtime'] == 'hermes':
        need(decoded(attributes.get('observed.run_id')) == receipt.get('run_id'), 'Stored observed native run differs')
    need(receipt.get('verified_task') is True and receipt.get('export_flushed') is True and
         all(decoded(attributes.get('verified.'+key)) == value for key,value in receipt['outcome'].items()),
         'Stored independently verified task outcome differs')
    successful = 0
    for event in spans[0]['events']:
        name = event.get('name');values = decoded(event.get('attributes',{}))
        need(isinstance(values,dict) and values.get('session_id') == receipt['binding']['session_id'], 'Stored observed event session differs')
        if receipt['runtime'] == 'hermes':
            need(values.get('run_id') == receipt['run_id'], 'Stored observed event run differs')
            if name in ('client.observed.run.completed','client.observed.run.cancelled','client.observed.run.failed'):
                need(set(values) == {'run_id','session_id'}, 'Stored observed terminal fields differ');continue
            need(name in ('client.observed.tool.started','client.observed.tool.completed') and values.get('tool') in TOOLS['hermes'] and
                 set(values) == ({'tool','run_id','session_id','error'} if name.endswith('completed') else {'tool','run_id','session_id'}), 'Stored observed tool fields differ')
            if name.endswith('completed'):
                need(type(values['error']) is bool, 'Stored observed tool outcome differs')
                successful += values['error'] is False
        else:
            status = values.get('status')
            need(status in ('pending','running','completed','error') and name == 'client.observed.tool.'+status and
                 values.get('tool') in TOOLS['opencode'] and set(values) == {'tool','session_id','status'}, 'Stored observed tool fields differ')
            successful += status == 'completed'
    need(successful > 0 and len(spans[0]['events']) == receipt['observed_event_count'], 'Stored successful tool evidence differs')
    return {'trace_id':receipt['trace_id'],'experiment_id':receipt['experiment_id'],'workspace':WORKSPACE,
            'stored_payload_scan':True,'capture_scope':COVERAGE}
