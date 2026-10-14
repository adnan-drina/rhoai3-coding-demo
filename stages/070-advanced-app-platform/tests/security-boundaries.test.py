"""Execute the revised enrollment and promotion boundaries without credentials or a cluster."""
import importlib.util
import fnmatch
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import yaml

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'gitops/stages/070-advanced-app-platform/base'

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,BASE/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

scm=load('secured_enrollment','pipelines/gitlab/reconcile.py')
promote=load('secured_promotion','pipelines/project-pipeline/promote.py')

class Coordinator(unittest.TestCase):
    def setUp(self):
        self.row={'project_id':42,'initial_commit':'1'*40,'kind':'application','requester':'user:default/ai-developer'}
        self.project={'id':42,'path':'example','namespace':{'id':7},'default_branch':'main'}
        self.config={'GITLAB_WORKLOAD_GROUP_ID':'7','GITLAB_REQUESTER_IDS':{'user:default/ai-developer':3},
                     'GITLAB_REQUESTER_NAMES':{'user:default/ai-developer':'platform-developer'},
                     'PLATFORM_REPO_URL':'https://gitlab.example.test/rhoai-platform/demo.git','PLATFORM_REVISION':'2'*40}
        self.api=Mock()
        self.api.request.side_effect=lambda method,path: ({'state':'active','username':'platform-developer'} if path=='users/3'
                                                        else {'access_level':30})
        self.writes=[]
        def oc(*args,document=None):
            if args[0]=='create': self.writes.append(document);return document
            if args[1]=='namespace':return {'metadata':{'labels':{'rhoai3.io/gitlab-project-id':'42'}}}
            return {'status':{'health':{'status':'Healthy'},'sync':{'status':'Synced','revision':'2'*40},'operationState':{'phase':'Succeeded'}}}
        self.oc=oc
    def enroll(self):
        with patch.object(scm,'oc',side_effect=self.oc),patch.object(scm,'apply',side_effect=self.writes.append),patch.object(scm,'mount_project_scanner'):
            scm.enroll(self.api,self.row,self.project,{'id':'1'*40,'parent_ids':[]},self.config)
    def test_only_platform_application_is_dispatched(self):
        self.enroll()
        self.assertEqual([r['kind'] for r in self.writes],['Application'])
        app=self.writes[0]
        self.assertEqual(app['spec']['project'],'platform-projects')
        self.assertEqual(app['spec']['source']['targetRevision'],'2'*40)
        self.assertNotIn('patches',app['spec']['source']['kustomize'])
        self.assertEqual(json.loads(app['spec']['source']['kustomize']['commonAnnotations']['rhoai3.io/enrollment']),self.row)
    def test_healthy_resources_do_not_hide_a_failed_bootstrap(self):
        original=self.oc
        def unfinished(*args,**kwargs):
            row=original(*args,**kwargs)
            if args[1]=='application':row['status']['operationState']['phase']='Failed'
            return row
        self.oc=unfinished
        with self.assertRaises(ValueError):self.enroll()
    def test_foreign_requester_is_refused_before_any_write(self):
        for ref in ('user:default/foreign','',None):
            self.row['requester']=ref
            with self.assertRaises(ValueError):self.enroll()
        self.assertEqual(self.writes,[])
    def test_blocked_or_nonmember_person_is_refused(self):
        for person,level in (({'state':'blocked','username':'platform-developer'},30),({'state':'active','username':'wrong'},30),({'state':'active','username':'platform-developer'},20)):
            self.api.request.side_effect=lambda method,path: person if path=='users/3' else {'access_level':level}
            with self.assertRaises(ValueError):self.enroll()
        self.assertEqual(self.writes,[])
    def test_existing_foreign_namespace_is_never_claimed(self):
        self.oc=lambda *args,**kwargs:{'metadata':{'labels':{'rhoai3.io/gitlab-project-id':'43'}}}
        with self.assertRaises(ValueError):self.enroll()
        self.assertEqual(self.writes,[])

    def test_missing_persona_name_mapping_is_refused(self):
        self.config.pop('GITLAB_REQUESTER_NAMES')
        with self.assertRaises(ValueError): self.enroll()
        self.assertEqual(self.writes,[])

    def test_migration_is_dispatched_only_after_native_bootstrap_succeeds(self):
        self.row['kind']='migration'
        self.config.update(GITLAB_WORKLOAD_GROUP='rhoai-workloads',GITLAB_BASE_URL='https://gitlab.example.test')
        with patch.object(scm,'provision_migration') as dispatch:
            self.enroll()
            dispatch.assert_called_once_with('example',self.row,self.project,self.config)
        self.oc=lambda *args,**kwargs: {'metadata':{'labels':{'rhoai3.io/gitlab-project-id':'42'}}}
        with patch.object(scm,'provision_migration') as dispatch:
            with self.assertRaises(ValueError): self.enroll()
            dispatch.assert_not_called()

    def test_existing_provisioning_cannot_hide_an_override_or_foreign_request(self):
        self.config.update(GITLAB_WORKLOAD_GROUP='rhoai-workloads',GITLAB_BASE_URL='https://gitlab.example.test')
        missing=subprocess.CalledProcessError(1,['oc'],stderr='(NotFound)')
        with patch.object(scm,'oc',side_effect=[missing,None]) as call:
            scm.provision_migration('example',self.row,self.project,self.config)
        expected=call.call_args_list[1].kwargs['document']
        with patch.object(scm,'oc',return_value=expected) as call:
            scm.provision_migration('example',self.row,self.project,self.config)
            self.assertEqual(call.call_count,1)
        for field,value in (('pipelineSpec',{}),('workspaces',[]),('taskRunSpecs',[]),('params',[])):
            altered=json.loads(json.dumps(expected));altered['spec'][field]=value
            with patch.object(scm,'oc',return_value=altered):
                with self.assertRaises(ValueError):scm.provision_migration('example',self.row,self.project,self.config)

class NativeProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        target=Path(cls.temp.name)/'pipelines';shutil.copytree(BASE/'pipelines',target)
        p=target/'project-enrollment/kustomization.yaml';d=yaml.safe_load(p.read_text())
        d['commonAnnotations']={'rhoai3.io/project-name':'test-example','rhoai3.io/project-namespace':'test-example-dev','rhoai3.io/enrollment':'{}'}
        p.write_text(yaml.safe_dump(d,sort_keys=False))
        cls.rows=list(yaml.safe_load_all(subprocess.check_output(['kustomize','build',str(p.parent)],text=True)))
        cls.objects={(r['kind'],r['metadata'].get('namespace'),r['metadata']['name']):r for r in cls.rows}
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_all_role_references_resolve_and_sa_namespace_is_explicit(self):
        for r in self.rows:
            if r['kind']=='RoleBinding':
                if r['roleRef']['kind']=='Role' and r['roleRef']['name']!='project-enrollment-inputs':
                    self.assertIn(('Role',r['metadata']['namespace'],r['roleRef']['name']),self.objects)
                for s in r['subjects']:
                    if s['kind']=='ServiceAccount':self.assertEqual(s['namespace'],'test-example-dev')
                    else:self.assertNotIn('namespace',s)
    def test_bootstrap_pod_receives_the_platform_enrollment_annotation(self):
        job=self.objects['Job','test-example-dev','project-enrollment']
        self.assertEqual(job['spec']['template']['metadata']['annotations']['rhoai3.io/enrollment'],'{}')
        self.assertEqual(job['spec']['template']['spec']['serviceAccountName'],'project-enrollment')

    def test_builder_scc_is_not_granted_to_runner_or_runtime(self):
        bindings=[r for r in self.rows if r['kind']=='RoleBinding' and r['roleRef']['name']=='pipeline-userns-builder']
        self.assertEqual(len(bindings),1)
        self.assertEqual(bindings[0]['subjects'],[{'kind':'ServiceAccount','name':'image-builder','namespace':'test-example-dev'}])
    def test_builder_constraint_requires_pod_isolation_and_no_host_authority(self):
        role = yaml.safe_load((BASE / 'pipelines/operators/image-builder-scc.yaml').read_text())
        self.assertEqual(role['rules'], [{'apiGroups':['security.openshift.io'], 'resources':['securitycontextconstraints'], 'resourceNames':['nested-container'], 'verbs':['use']}])
        self.assertFalse((BASE / 'pipelines/operators/pipeline-userns-builder-scc.yaml').exists())
        task = yaml.safe_load((BASE / 'pipelines/project-pipeline/task-build-image.yaml').read_text())['spec']
        step = task['steps'][0]
        self.assertEqual(step['securityContext'], {'runAsNonRoot':True, 'runAsUser':1000, 'allowPrivilegeEscalation':True, 'procMount':'Unmasked', 'capabilities':{'add':['SETUID','SETGID']}})
        self.assertFalse(step['securityContext'].get('privileged',False))
        self.assertFalse(any('hostPath' in v for v in task['volumes']))
        self.assertIn('Refusing build outside the required mapped pod user namespace', step['script'])
        maps = self.objects['ConfigMap','test-example-dev','buildah-userns-mappings']['data']
        self.assertEqual(maps, {'subuid':'build:1001:64535\n','subgid':'build:1001:64535\n'})
        _,start,count=maps['subuid'].strip().split(':')
        self.assertEqual(int(start)+int(count),65536)
        self.assertEqual(len([m for m in step['volumeMounts'] if m['name']=='idmaps' and m.get('readOnly')]),2)

    def test_cross_namespace_reads_name_only_this_project(self):
        r=self.objects['Role','openshift-gitops','test-example.readback']
        self.assertEqual(r['rules'],[{'apiGroups':['argoproj.io'],'resources':['applications'],'verbs':['get'],'resourceNames':['runtime-test-example']}])
        r=self.objects['Role','app-platform-build','test-example.runs']
        self.assertEqual(r['rules'][0]['resourceNames'],['migration-source-test-example'])
        self.assertEqual(r['rules'][0]['verbs'],['get'])
        self.assertFalse(any('pipelineruns' in rule['resources'] for rule in r['rules']))
        policy=yaml.safe_load((BASE/'pipelines/gitlab/provisioning-policy.yaml').read_text())
        self.assertEqual(policy['spec']['validations'],[{'expression':'false','message':'Only the platform coordinator may dispatch migration provisioning'}])
    def test_runtime_project_has_no_cluster_or_rbac_authority(self):
        p=yaml.safe_load((BASE/'pipelines/gitlab/runtime-projects.yaml').read_text())['spec']
        self.assertEqual(p['clusterResourceWhitelist'],[])
        self.assertEqual({r['kind'] for r in p['namespaceResourceWhitelist']},set(promote.KINDS))
        self.assertNotIn('*',p['sourceRepos'])
        self.assertEqual(p['destinations'],[{'server':'https://kubernetes.default.svc','namespace':'*-dev'}])
    def test_repository_allowlists_match_the_native_route_and_owned_groups_only(self):
        host='gitlab-gitlab-system.apps.example.test'
        for name,path in (('platform-projects','rhoai-platform/rhoai3-coding-demo.git'),('runtime-projects','rhoai-delivery/example-deployment.git')):
            p=yaml.safe_load((BASE/('pipelines/gitlab/'+name+'.yaml')).read_text())
            patterns=p['spec']['sourceRepos']
            self.assertTrue(any(fnmatch.fnmatchcase('https://'+host+'/'+path,x) for x in patterns))
            for url in ('https://foreign.apps.example.test/'+path,'https://'+host+'/rhoai-workloads/example.git'):
                self.assertFalse(any(fnmatch.fnmatchcase(url,x) for x in patterns))
    def test_coordinator_has_no_secret_or_rbac_write(self):
        rs=list(yaml.safe_load_all((BASE/'pipelines/gitlab/reconciler.yaml').read_text()))
        cluster=next(r for r in rs if r['kind']=='ClusterRole' and r['metadata']['name']=='project-provisioner')
        self.assertEqual(cluster['rules'],[{'apiGroups':[''],'resources':['namespaces'],'verbs':['get','create']}, {'apiGroups':[''],'resources':['secrets'],'resourceNames':['sonarqube-credentials'],'verbs':['get']}])
        for r in rs:
            if r['kind']=='Role' and r['metadata']['name'].startswith('project-provisioner'):
                for rule in r['rules']:
                    if 'secrets' in rule['resources'] or 'configmaps' in rule['resources']:
                        self.assertEqual(rule['verbs'],['get']);self.assertTrue(rule['resourceNames'])

class PortalContract(unittest.TestCase):
    def test_application_parameters_start_denying_before_the_binding_exists(self):
        setup=(BASE/'gitlab/configure-argocd-reader.py').read_text()
        self.assertIn("'ready':'false'",setup)
        self.assertIn("'(AlreadyExists)'",setup)
        reader=list(yaml.safe_load_all((BASE/'gitlab/argocd-reader.yaml').read_text()))
        hook=next(r for r in reader if r['kind']=='Job')
        self.assertEqual(hook['metadata']['annotations']['argocd.argoproj.io/sync-wave'],'0')
        policy=yaml.safe_load((BASE/'pipelines/gitlab/application-policy.yaml').read_text())
        self.assertIn("params.data['ready'] == 'true'",policy['spec']['validations'][0]['expression'])
        self.assertIn("'ready':'true'",(BASE/'gitlab/bootstrap-scm.py').read_text())

    def test_only_admins_register_and_discovery_does_not_ingest_templates(self):
        cfg=yaml.safe_load(yaml.safe_load((BASE/'rhdh/rhdh-instance/app-config-configmap.yaml').read_text())['data']['app-config-rhdh.yaml'])
        self.assertTrue(cfg['permission']['enabled'])
        self.assertEqual(cfg['permission']['rbac']['admin']['users'],[{'name':'user:default/ai-admin'}])
        self.assertNotIn('Template',cfg['catalog']['rules'][0]['allow'])
        self.assertIn('Template',cfg['catalog']['locations'][0]['rules'][0]['allow'])
        provider=cfg['catalog']['providers']['gitlab']['workloads']
        self.assertEqual((provider['group'],provider['branch'],provider['entityFilename']),('rhoai-workloads','main','catalog-info.yaml'))
        for name in ('agentic-quarkus-scaffold','app-migration'):
            steps=yaml.safe_load((BASE/('rhdh/templates/'+name+'/template.yaml')).read_text())['spec']['steps']
            self.assertNotIn('catalog:register',[r['action'] for r in steps])
            issue=next(r for r in steps if r['action']=='gitlab:issues:create')
            self.assertIn('"requester": "${{ user.ref }}"',issue['input']['description'])
    def test_auto_created_accounts_are_blocked(self):
        values=yaml.safe_load((BASE/'gitlab/values.yaml').read_text())
        self.assertTrue(values['global']['appConfig']['omniauth']['blockAutoCreatedUsers'])

class OperatorChannel(unittest.TestCase):
    def test_actual_validator_pattern_accepts_only_selected_minor(self):
        script=(ROOT/'stages/070-advanced-app-platform/validate.sh').read_text()
        pattern_line=next(line.strip() for line in script.splitlines() if line.strip().startswith('pattern='))
        for actual,expected in (('openshift-pipelines-operator-rh.v1.24.0',0),('openshift-pipelines-operator-rh.v1.24.1',0),('openshift-pipelines-operator-rh.v1.25.0',1),('openshift-pipelines-operator-rh.v1X24X1',1),('',1)):
            env=dict(os.environ,CSV_PIN='openshift-pipelines-operator-rh.v1.24.',ACTUAL=actual)
            result=subprocess.run(['bash','-c','csv="$CSV_PIN"; '+pattern_line+'; printf "%s" "$ACTUAL" | grep -q -E "$pattern"'],env=env,capture_output=True)
            self.assertEqual(result.returncode,expected)


class DeliveryBranch(unittest.TestCase):
    def test_correct_policy_reuses_existing_protection(self):
        api=Mock();api.request.return_value={'allow_force_push':False,'push_access_levels':[{'access_level':30}]}
        scm.ensure_delivery_branch(api,42,False)
        self.assertEqual(api.request.call_count,1)
    def test_changed_protection_after_token_issuance_is_refused(self):
        api=Mock();api.request.return_value={'allow_force_push':True,'push_access_levels':[{'access_level':40}]}
        with self.assertRaises(ValueError):scm.ensure_delivery_branch(api,42,False)
        self.assertEqual(api.request.call_count,1)
    def test_initial_setup_uses_free_api_and_reads_back(self):
        api=Mock();api.request.side_effect=[{'allow_force_push':False,'push_access_levels':[{'access_level':40}]},None,None,{'allow_force_push':False,'push_access_levels':[{'access_level':30}]}]
        scm.ensure_delivery_branch(api,42,True)
        self.assertEqual([c.args[0] for c in api.request.call_args_list],['GET','DELETE','POST','GET'])
        payload=api.request.call_args_list[2].args[2]
        self.assertEqual(payload,{'name':'main','push_access_level':30,'merge_access_level':40,'allow_force_push':False})


class SourcePromotion(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'source';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Test');self.git('config','user.email','test@example.invalid')
        (self.repo/'k8s').mkdir();(self.repo/'k8s/runtime.json').write_text('{"proof":"committed"}')
        self.git('add','.');self.git('commit','-qm','first');self.sha=self.git('rev-parse','HEAD').decode().strip()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.PIPE)
    def test_build_workspace_and_replace_refs_do_not_change_source_artifact(self):
        (self.repo/'k8s/runtime.json').write_text('{"proof":"forged"}')
        self.git('commit','-qam','forged');bad=self.git('rev-parse','HEAD').decode().strip()
        self.git('replace',self.sha,bad)
        clean=self.root/'promote';clean.mkdir()
        actual=subprocess.check_output
        seen=[]
        def checked(argv,**kwargs):seen.append((argv,kwargs));return actual(argv,**kwargs)
        with patch.dict(os.environ,{'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'core.hooksPath','GIT_CONFIG_VALUE_0':'/attacker','GIT_DIR':str(self.repo/'.git'),'GIT_WORK_TREE':str(self.repo)}),patch.object(promote.subprocess,'check_output',side_effect=checked):
            git=promote.clean_git(clean,'https://gitlab-gitlab-system.example.test/rhoai-workloads/example.git',Path('/safe/credentials'))
        self.assertTrue(all('GIT_CONFIG_COUNT' not in env['env'] and 'GIT_DIR' not in env['env'] for _,env in seen))
        self.assertTrue(all('--no-replace-objects' in argv for argv,_ in seen))
        # Populate the fresh bare repo with the fixture, never copy its configuration/refs.
        actual(['git','-C',str(clean),'fetch','-q',str(self.repo),self.sha])
        output=self.root/'artifacts';output.mkdir();promote.committed_artifacts(git,self.sha,output)
        self.assertEqual(next(output.iterdir()).read_text(),'{"proof":"committed"}')
        self.assertFalse((clean/'refs/replace').exists())
    def test_committed_symlink_cannot_supply_runtime_manifests(self):
        (self.repo/'k8s/link.yaml').symlink_to('/sensitive')
        self.git('add','.');self.git('commit','-qm','link');sha=self.git('rev-parse','HEAD').decode().strip()
        output=self.root/'out';output.mkdir()
        with self.assertRaises(ValueError):promote.committed_artifacts(self.git,sha,output)
    def test_promotion_task_never_mounts_the_build_workspace(self):
        task=yaml.safe_load((BASE/'pipelines/project-pipeline/task-promote.yaml').read_text())['spec']
        self.assertNotIn('workspaces',task)
        self.assertFalse(any('persistentVolumeClaim' in v for v in task['volumes']))
        self.assertNotIn('argocd-delivery-reader',json.dumps(task))
    def test_route_subdomain_is_refused(self):
        deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'example'},'spec':{'template':{'spec':{'containers':[{'name':'example','image':'old'}]}}}}
        route={'apiVersion':'route.openshift.io/v1','kind':'Route','metadata':{'name':'example'},'spec':{'subdomain':'other-project','to':{'name':'example'}}}
        image='image-registry.openshift-image-registry.svc:5000/example-dev/example@sha256:'+'a'*64
        with self.assertRaises(ValueError):promote.validate_runtime([deployment,route],'example','example-dev',image)

if __name__=='__main__':unittest.main()
