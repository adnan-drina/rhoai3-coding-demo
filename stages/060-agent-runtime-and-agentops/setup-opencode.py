#!/usr/bin/env python3
"""Owned persistent OpenCode setup; native API/CLI only, never generated Pod edits."""
import argparse
import base64
import hashlib
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import yaml
from native_api import guarded, oc, need, native_gateway, persona

ROOT = Path(__file__).resolve().parents[2]
INPUTS = Path(__file__).with_name('opencode')
NAME = 'opencode'
WORKSPACE = 'ai-agents'
PROVIDER = 'opencode-maas-qwen38'
SUBSCRIPTION = 'opencode-private-qwen38'
MODEL = 'publishers/internal-models/models/qwen3-8-27b-int4'
DIGEST = 'sha256:86922260052003a80883880b40fa4245ae7645b25a4ee5f988ec7f1daca93d09'
module = importlib.util.spec_from_file_location('inference_checks', Path(__file__).with_name('qualify-inference.py'))
checks = importlib.util.module_from_spec(module); module.loader.exec_module(checks)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Setup:
    def __init__(self, args):
        self.args = args
        self.env, self.user_token = persona(args.persona_kubeconfig, 'ai-admin')
        self.bootstrap_env = guarded(os.environ['KUBECONFIG'])
        need(oc(self.env,'whoami','--show-server')==oc(self.bootstrap_env,'whoami','--show-server'),'Persona and bootstrap target different clusters')
        self.cli = Path(os.environ['RHOAI_STAGE060_OPENSHELL_CLI'])
        pins = json.loads((ROOT/'gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json').read_text())
        need(hashlib.sha256(self.cli.read_bytes()).hexdigest() == pins['cliBinarySha256'] and pins['sourceCommit']=='12cec59bf4c36c305032143eb90870bd16d8820b', 'Native CLI/source pin differs')
        self.gateway_pin=pins['images']['gateway']
        self.directory = Path(args.state_dir)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        need(not self.directory.is_symlink() and self.directory.stat().st_mode & 0o077 == 0, 'Use an owner-only recovery directory')
        self.journal = self.directory/'state.json'
        need(not self.journal.exists() or (not self.journal.is_symlink() and self.journal.stat().st_mode & 0o077 == 0), 'Unsafe recovery journal')
        self.state = json.loads(self.journal.read_text()) if self.journal.exists() else {}
        need(not self.state or self.state.get('workspace') == WORKSPACE, 'Foreign recovery state')
        self.template = json.loads((INPUTS/'template.json').read_text())
        self.receipt = {'workspace':WORKSPACE,'sandbox':NAME,'model':MODEL,'checks':{},'changes':[]}

    def get(self, kind, name, namespace):
        return json.loads(oc(self.bootstrap_env, 'get',kind,name,'-n',namespace,'-o','json'))

    def save(self, **fields):
        self.state.update(fields, workspace=WORKSPACE)
        pending=self.journal.with_suffix('.pending')
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(self.state,stream);stream.flush();os.fsync(stream.fileno())
        pending.replace(self.journal)

    def preflight(self):
        app=self.get('application','openshell-runtime','openshift-gitops')
        need(app['spec']['source']['targetRevision']==self.args.revision and app['status']['sync']['revision']==self.args.revision and app['status']['sync']['status']=='Synced' and app['status']['health']['status']=='Healthy' and not app.get('operation'),'Exact runtime revision is not ready')
        need(subprocess.check_output(['git','-C',str(ROOT),'show',self.args.revision+':'+str(Path(__file__).resolve().relative_to(ROOT))])==Path(__file__).read_bytes(),'Published helper differs')
        for path in [Path(__file__).with_name('native_api.py'),Path(__file__).with_name('qualify-inference.py'),ROOT/'gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json']:
            need(subprocess.check_output(['git','-C',str(ROOT),'show',self.args.revision+':'+str(path.relative_to(ROOT))])==path.read_bytes(),'Published executable dependency differs')
        for p in INPUTS.iterdir():
            if p.is_file():need(subprocess.check_output(['git','-C',str(ROOT),'show',self.args.revision+':'+str(p.relative_to(ROOT))])==p.read_bytes(),'Published runtime input differs')
        gateway_runtime=self.get('statefulset','openshell','openshell')
        image=gateway_runtime['spec']['template']['spec']['containers'][0]['image']
        need(image.split('@')[0].split(':')[0]==self.gateway_pin['repository'] and image.endswith('@'+self.gateway_pin['amd64Digest']) and gateway_runtime.get('status',{}).get('readyReplicas')==1,'Gateway does not match the ready pinned runtime')
        subscription=self.get('maassubscription',SUBSCRIPTION,'models-as-a-service')
        desired_subscription=yaml.safe_load((ROOT/'gitops/stages/060-agent-runtime-and-agentops/runtime/opencode/subscription.yaml').read_text())['spec']
        need(subscription['spec']==desired_subscription,'Dedicated subscription differs from its complete reviewed scope')
        need(subscription['spec']['owner']=={'users':['ai-admin']} and len(subscription['spec']['modelRefs'])==1 and subscription['spec']['modelRefs'][0]['name']=='qwen3-8-27b-int4' and subscription['spec']['modelRefs'][0]['namespace']=='internal-models','Private subscription scope differs')
        need(any(c.get('type')=='Ready' and c.get('status')=='True' and c.get('observedGeneration')==subscription['metadata']['generation'] for c in subscription.get('status',{}).get('conditions',[])),'Dedicated subscription is not Ready')
        stream=self.get('imagestreamtag','opencode-runtime:1.18.16',WORKSPACE)
        need(stream['image']['metadata']['name']==DIGEST,'Rehomed immutable image is absent')
        gateway=self.get('gateway','maas-default-gateway','openshift-ingress')
        host=[v['hostname'] for v in gateway['spec']['listeners'] if v['name']=='api']
        need(len(host)==1,'Common MaaS listener is ambiguous');self.host=host[0];self.api='https://'+self.host
        serving=self.get('llminferenceservice','qwen3-8-27b-int4','internal-models')
        need('--max-model-len=262144' in json.dumps(serving['spec']),'OpenCode context limit differs from actual serving configuration')
        status,catalog=checks.http(self.api+'/v1/models',self.user_token)
        need(status==200 and any(m.get('id')==MODEL and m.get('ready') for m in catalog.get('data',[])),'Canonical Qwen model is not available to ai-admin')
        status,subscriptions=checks.http(self.api+'/v1/subscriptions',self.user_token)
        entries=[v for v in subscriptions or [] if v.get('subscription_id_header')==SUBSCRIPTION]
        need(status==200 and len(entries)==1,'Dedicated native subscription is not discoverable')
        self.subscription_header=entries[0]['subscription_id_header']

    def inventory(self):
        identity=self.owner.run(['whoami','-o','json'])
        members=self.admin.run(['workspace','member','list','--workspace',WORKSPACE,'-o','json'])
        need(not members.get('next_page_token') and len(members['members'])==1 and members['members'][0]['role']=='admin' and members['members'][0]['subject']==identity['subject'] and identity['display_name']=='ai-admin','Genuine immutable workspace administrator differs')
        need('openshell-user' in identity.get('roles',[]) and 'openshell-platform-admin' not in identity.get('roles',[]),'Native owner role is outside the reviewed workspace scope')
        workspaces=self.admin.run(['workspace','list','-o','json']);need(not workspaces.get('next_page_token'),'Workspace inventory incomplete')
        workspace=[w for w in workspaces['workspaces'] if w['name']==WORKSPACE];need(len(workspace)==1,'Native hosting workspace is ambiguous')
        binding={'server':oc(self.bootstrap_env,'whoami','--show-server'),'issuer':self.get('configmap','openshell-identity','openshell')['data']['issuer'],'gateway_uid':self.get('statefulset','openshell','openshell')['metadata']['uid'],'namespace_uid':self.get('namespace',WORKSPACE,WORKSPACE)['metadata']['uid'],'workspace_id':workspace[0]['id'],'subject':identity['subject'],'source_input_hash':digest({p.name:p.read_text() for p in INPUTS.iterdir() if p.is_file()})}
        need(not self.state.get('binding') or self.state['binding']==binding,'Recovery cluster/owner/workspace/source binding differs; overwrite refused')
        self.owner.identity_verified=True
        self.save(binding=binding)
        self.fleet=self.admin.run(['sandbox','list','--all-workspaces','-o','json'])
        need(not self.fleet.get('next_page_token'),'Fleet inventory is incomplete')
        self.policy=self.admin.run(['policy','get','--global','--full','-o','json'])
        providers=self.owner.run(['provider','list','-o','json'],WORKSPACE);templates=self.owner.run(['sandbox','template','list','-o','json'],WORKSPACE)
        need(not providers.get('next_page_token') and not templates.get('next_page_token'),'Native provider/template inventory incomplete')
        self.providers=providers['providers'];self.templates=templates['templates']

    def policy_input(self):
        authored=yaml.safe_load((INPUTS/'policy.yaml').read_text().replace('__MAAS_COMMON_HOST__',self.host))
        original=self.state.get('original_policy',self.policy['policy'])
        need(original.get('filesystem_policy')==authored['filesystem_policy'] and original.get('landlock')==authored['landlock'],'Original filesystem or Landlock denials differ')
        self.intended=dict(original,network_policies=authored['network_policies'])
        if self.policy['policy']==self.intended:return
        need(self.args.apply and not self.fleet['sandboxes'] and original.get('network_policies',{})=={} and self.policy['hash']==self.args.expected_policy_hash,'Durable global policy requires the reviewed unchanged empty-fleet baseline')
        self.save(original_policy=original,original_policy_hash=self.policy['hash'])
        target=self.directory/'policy.json';target.write_text(json.dumps(self.intended));target.chmod(0o600)
        current=self.admin.run(['policy','get','--global','--full','-o','json']);need(current['hash']==self.policy['hash'],'Concurrent global policy change; refused')
        fleet=self.admin.run(['sandbox','list','--all-workspaces','-o','json']);need(not fleet.get('next_page_token') and fleet.get('sandboxes')==[],'Concurrent fleet change before global policy update; refused')
        self.admin.run(['policy','set','--global','--yes','--policy',str(target)],structured=False)
        applied=self.admin.run(['policy','get','--global','--full','-o','json']);need(applied['policy']==self.intended,'Applied global policy differs')
        self.save(applied_policy_hash=applied['hash']);self.receipt['changes'].append('durable-global-policy')

    def provision(self):
        profile_file=self.directory/'profile.yaml';profile_file.write_text((INPUTS/'profile.yaml').read_text().replace('__MAAS_COMMON_HOST__',self.host))
        profiles=self.owner.run(['profile','list','-o','json'],WORKSPACE)
        found=[v for v in profiles if v['id']==PROVIDER]
        if not found:
            self.owner.run(['profile','lint','-f',str(profile_file)],WORKSPACE,structured=False)
            self.save(profile_pending=True)
            self.owner.run(['profile','import','-f',str(profile_file)],WORKSPACE,structured=False)
            exported=self.owner.run(['profile','export',PROVIDER,'-o','json'],WORKSPACE);self.save(profile_hash=digest(exported),profile_pending=False)
        else:
            exported=self.owner.run(['profile','export',PROVIDER,'-o','json'],WORKSPACE)
            need(self.state.get('profile_hash')==digest(exported),'Existing profile is foreign or changed; import refused')
        found=[v for v in self.providers if v['name']==PROVIDER]
        if not found:
            need(not self.state.get('key_id') and not self.state.get('key_pending'),'Pending owned key requires explicit recovery/revocation before another mint')
            self.save(key_pending=True,key_name='opencode-runtime-qwen38')
            status,created=checks.http(self.api+'/v1/api-keys',self.user_token,{'name':'opencode-runtime-qwen38','subscription':self.subscription_header,'expiresIn':'30d','ephemeral':False})
            need(status==201 and created.get('id'),'Native persistent key creation failed')
            self.save(key_id=created['id'],key_pending=True)
            need(created.get('subscription')==self.subscription_header and created.get('ephemeral') is False and created.get('key'),'Persistent key binding differs')
            expiration=created.get('expiresAt')
            expiry=datetime.fromisoformat(expiration.replace('Z','+00:00')).timestamp() if isinstance(expiration,str) else 0
            need(time.time()+86400 < expiry <= time.time()+31*86400,'Native key expiry is outside the reviewed30day duration')
            self.save(key_expiry=expiration,key_owner='ai-admin',key_subscription=self.subscription_header,key_hash=hashlib.sha256(created['key'].encode()).hexdigest())
            metadata_status,metadata=checks.http(self.api+'/v1/api-keys/'+created['id'],self.user_token)
            need(metadata_status==200 and metadata.get('username')=='ai-admin' and metadata.get('subscription')==SUBSCRIPTION and metadata.get('status')=='active' and metadata.get('tenant'),'New persistent key owner/scope metadata differs')
            self.save(key_tenant=metadata['tenant'])
            self.owner.run(['provider','create','--name',PROVIDER,'--type',PROVIDER,'--credential','MAAS_API_KEY','--config','owner=rhoai3-coding-demo','--config','maas_key_id='+created['id']],WORKSPACE,credentials={'MAAS_API_KEY':created['key']},structured=False)
            self.owner.run(['provider','update',PROVIDER,'--credential-expires-at','MAAS_API_KEY='+str(int(expiry*1000)),'--wait'],WORKSPACE,structured=False)
            provider=[v for v in self.owner.run(['provider','list','-o','json'],WORKSPACE)['providers'] if v['name']==PROVIDER]
            need(len(provider)==1,'Created provider is ambiguous');self.save(provider_id=provider[0]['id'],provider_hash=digest(provider[0]),key_pending=False)
        else:need(len(found)==1 and self.state.get('provider_id')==found[0]['id'] and self.state.get('provider_hash')==digest(found[0]),'Foreign or changed provider; adoption refused')
        found=[v for v in self.templates if v['name']==NAME]
        if not found:
            arguments=['sandbox','template','create',NAME,'--image',self.template['image'],'--cpu',self.template['cpu'],'--memory',self.template['memory'],'-o','json']
            for key,value in self.template['env'].items():arguments+=['--env',key+'='+value]
            for key,value in self.template['labels'].items():arguments+=['--label',key+'='+value]
            template=self.owner.run(arguments,WORKSPACE);self.save(template_id=template['id'],template_hash=digest(template))
        else:need(len(found)==1 and self.state.get('template_id')==found[0]['id'] and found[0]['image']==self.template['image'] and found[0].get('environment')==self.template['env'] and found[0].get('resources')=={'cpu':self.template['cpu'],'memory':self.template['memory']} and found[0].get('labels')==self.template['labels'] and not found[0].get('driver_config') and not found[0].get('startup') and digest(found[0])==self.state.get('template_hash'),'Foreign or changed template; takeover refused')
        self.policy_input()
        owned=[v for v in self.fleet['sandboxes'] if v.get('name')==NAME and v.get('workspace')==WORKSPACE]
        if owned:
            need(len(owned)==1 and owned[0]['id']==self.state.get('sandbox_id'),'Foreign or pending unknown sandbox; takeover refused')
            if not self.state.get('sandbox_pending'):
                current=self.owner.run(['sandbox','get',NAME,'-o','json'],WORKSPACE)
                need(self.sandbox_record(current)==self.state.get('sandbox_record'),'Existing owned sandbox provenance changed')
                return
        need(owned or not self.state.get('sandbox_id'),'Existing owned sandbox disappeared; preserving recovery state')
        upload=self.directory/'upload';(upload/'state/auth').mkdir(parents=True,exist_ok=True,mode=0o700);(upload/'workspace').mkdir(exist_ok=True,mode=0o700)
        password=upload/'state/auth/server-password'
        if not password.exists():password.write_text(secrets.token_urlsafe(48));password.chmod(0o600)
        need(not password.is_symlink() and password.stat().st_mode & 0o077==0,'Unsafe local listener secret')
        (upload/'state/start.sh').write_bytes((INPUTS/'start.sh').read_bytes());(upload/'state/start.sh').chmod(0o700)
        (upload/'workspace/opencode.json').write_text((INPUTS/'config.json').read_text().replace('__MAAS_COMMON_HOST__',self.host))
        if not owned:
            need(not self.state.get('sandbox_pending'),'Unknown create outcome; exact-ID review required, new creation refused')
            self.save(sandbox_pending=True)
            command='for attempt in {1..180}; do if [[ -f /sandbox/state/setup-ready ]]; then exec /bin/bash /sandbox/state/start.sh; fi; sleep 1; done; exit 1'
            created=self.owner.run(['sandbox','create','--name',NAME,'--template',NAME,'--provider',PROVIDER,'--no-auto-providers','--approval-mode','manual','--detach','--restart-policy','on-failure','--label','demo.rhoai.io/runtime=opencode','-o','json','--','/bin/bash','-c',command],WORKSPACE,timeout=240)
            need(created.get('id'),'Creation reply lacks exact native sandbox ID; preserve pending state')
            self.save(sandbox_id=created['id'])
        sandbox=self.owner.run(['sandbox','get',NAME,'-o','json'],WORKSPACE)
        need(sandbox['id']==self.state['sandbox_id'],'Sandbox changed before authenticated upload')
        for child in ('state','workspace'):
            self.owner.run(['sandbox','upload',NAME,str(upload/child),'/sandbox','--no-git-ignore'],WORKSPACE,structured=False,timeout=90)
        self.owner.run(['sandbox','exec','--name',NAME,'--no-tty','--no-login-shell','--','/bin/bash','-c','set -euo pipefail; test -f /sandbox/state/start.sh; test -f /sandbox/workspace/opencode.json; test ! -L /sandbox/state/auth/server-password; test -s /sandbox/state/auth/server-password; test "$(stat -c %a /sandbox/state/auth/server-password)" = 600; test "$(stat -c %u /sandbox/state/auth/server-password)" = "$(id -u)"; umask 077; printf ready > /sandbox/state/.setup-ready; mv /sandbox/state/.setup-ready /sandbox/state/setup-ready'],WORKSPACE,structured=False)
        final=self.owner.run(['sandbox','get',NAME,'-o','json'],WORKSPACE)
        self.save(sandbox_pending=False,sandbox_record=self.sandbox_record(final))
        self.receipt['changes'].append('persistent-opencode')

    def key_metadata(self):
        status,metadata=checks.http(self.api+'/v1/api-keys/'+self.state['key_id'],self.user_token)
        need(status==200 and metadata.get('id')==self.state['key_id'] and metadata.get('name')=='opencode-runtime-qwen38' and metadata.get('username')=='ai-admin' and metadata.get('subscription')==SUBSCRIPTION and metadata.get('ephemeral') is False and metadata.get('status')=='active' and metadata.get('tenant')==self.state.get('key_tenant'),'Owned key metadata/owner/model subscription is not active')
        need(datetime.fromisoformat(metadata.get('expirationDate','').replace('Z','+00:00')).timestamp()==datetime.fromisoformat(self.state['key_expiry'].replace('Z','+00:00')).timestamp(),'Key expiry differs from native creation metadata')
        need(datetime.fromisoformat(metadata['expirationDate'].replace('Z','+00:00')).timestamp()>time.time(),'Owned key expired; explicit reviewed rotation required')


    @staticmethod
    def sandbox_record(value):
        return {k:value.get(k) for k in ('id','name','workspace','labels','created_from_workload_template','restart_policy','policy_source')}

    def check(self):
        sandbox=self.owner.run(['sandbox','get',NAME,'-o','json'],WORKSPACE)
        need(sandbox['id']==self.state.get('sandbox_id') and self.sandbox_record(sandbox)==self.state.get('sandbox_record'),'Owned sandbox identity/provenance/restart policy differs')
        need(sandbox.get('restart_policy')=='on-failure' and sandbox.get('policy_source')=='global' and sandbox.get('created_from_workload_template',{}).get('name')==NAME,'Sandbox native template/global-policy contract differs')
        policy=self.admin.run(['policy','get','--global','--full','-o','json']);need(policy['policy']==self.intended,'Durable policy changed')
        providers=self.owner.run(['provider','list','-o','json'],WORKSPACE);need(not providers.get('next_page_token'),'Provider check inventory incomplete')
        matches=[v for v in providers['providers'] if v['id']==self.state.get('provider_id') and v['name']==PROVIDER]
        need(len(matches)==1 and matches[0].get('type')==PROVIDER and digest(matches[0])==self.state.get('provider_hash'),'Owned provider type/credentials/config/expiry metadata differs')
        self.key_metadata()
        self.receipt['checks'].update(native_identity=True,persistent_policy=True,owned_provider=True)
        self.receipt.update(sandbox_id=sandbox['id'],provider_id=self.state['provider_id'],key_id=self.state['key_id'],key_expiry=self.state['key_expiry'],subscription=self.state['key_subscription'])

    def run(self):
        self.preflight()
        with native_gateway(self.bootstrap_env,self.cli) as admin, native_gateway(self.bootstrap_env,self.cli,self.args.persona_home) as owner:
            self.admin,self.owner=admin,owner;self.inventory()
            if self.args.apply:self.provision()
            else:self.policy_input()
            self.check()
        print(json.dumps(self.receipt))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision',required=True)
    p.add_argument('--persona-home',default=os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'),required=not os.environ.get('RHOAI_STAGE060_ADMIN_CLI_HOME'))
    p.add_argument('--persona-kubeconfig',default=os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'),required=not os.environ.get('RHOAI_STAGE060_ADMIN_KUBECONFIG'))
    p.add_argument('--state-dir',default='/private/tmp/060-opencode-state')
    p.add_argument('--expected-policy-hash')
    p.add_argument('--apply',action='store_true')
    args=p.parse_args();Setup(args).run()


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('[FAIL] '+(str(error) if isinstance(error,RuntimeError) else 'Bounded native setup failed; inspect only the private recovery journal'))
        raise SystemExit(1)
