#!/usr/bin/env python3
"""Render pinned upstream charts into ordinary, checked-in Kustomize resources.

Helm is an authoring dependency only. Neither Argo CD nor a workload operator
renders these charts at deployment. Run with --check before publishing changes.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'
LOCK = Path(__file__).with_name('stage070-charts.lock.json')
CLI_IMAGE = 'registry.redhat.io/openshift4/ose-cli@sha256:69762925e16053d77685ff3a08b3b45dd2bfa5d68277851bc6969b368bbd0cb9'


class Dumper(yaml.SafeDumper):
    pass


def string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value,
                                   style='|' if '\n' in value else None)


Dumper.add_representer(str, string)


def dump(document):
    return yaml.dump(document, Dumper=Dumper, sort_keys=False, width=1000)


def annotate(document, wave):
    meta = document['metadata']
    meta.setdefault('labels', {}).update({'app.kubernetes.io/managed-by': 'argocd',
                                          'app.kubernetes.io/part-of': 'developer-platform'})
    annotations = meta['annotations'] = meta.get('annotations') or {}
    for key in list(annotations):
        if key.startswith('helm.sh/'):
            del annotations[key]
    annotations['argocd.argoproj.io/sync-wave'] = str(wave)


def gitlab_documents(documents, images):
    runtime = {'gitlab-runtime-buckets': {feature: 'pending-' + feature for feature in
                ('lfs', 'artifacts', 'uploads', 'packages', 'backups', 'backup-tmp')}}
    result = []
    release = None
    for document in documents:
        kind, name = document['kind'], document['metadata']['name']
        if name == 'gitlab-webservice-tests':
            continue
        if name == 'gitlab-gitlab-chart-info':
            release = document['data']
            continue  # Last successful version is written only after migration/readiness.
        if kind == 'Secret':
            raise ValueError('Unexpected chart-rendered credential; use the secret-generation hook')
        if kind in ('Ingress', 'Gateway', 'HTTPRoute', 'Certificate', 'Issuer', 'GitLab'):
            raise ValueError('Unexpected runtime chart/ingress dependency: ' + kind)
        document['metadata']['namespace'] = 'gitlab-system'
        wave = 3
        if kind == 'Job':
            wave = 5 if name.startswith('gitlab-shared-secrets-') else 9
            if name.startswith('gitlab-shared-secrets-'):
                document['metadata']['name'] = 'gitlab-shared-secrets'
            elif name.startswith('gitlab-migrations-'):
                document['metadata']['name'] = 'gitlab-migrations'
            elif name == 'gitlab-gitlab-upgrade-check':
                # Keep the upstream version check, wrapping initial-install/retry handling.
                wave = 4
                pod = document['spec']['template']['spec']
                pod['serviceAccountName'] = 'gitlab-bootstrap'
                pod['automountServiceAccountToken'] = True
                pod['containers'][0].update({'image': CLI_IMAGE,
                    'command': ['python3', '/bootstrap/bootstrap.py', 'check-upgrade']})
                pod['containers'][0]['volumeMounts'].extend([
                    {'name': 'bootstrap', 'mountPath': '/bootstrap', 'readOnly': True},
                    {'name': 'runtime', 'mountPath': '/runtime', 'readOnly': True}])
                pod['volumes'].extend([
                    {'name': 'bootstrap', 'configMap': {'name': 'gitlab-bootstrap'}},
                    {'name': 'runtime', 'configMap': {'name': 'gitlab-runtime-templates'}}])
            else:
                raise ValueError('Unmapped chart hook: ' + name)
            document['spec']['activeDeadlineSeconds'] = 1800
            document['metadata'].setdefault('annotations', {}).update({
                'argocd.argoproj.io/hook': 'Sync',
                'argocd.argoproj.io/hook-delete-policy': 'BeforeHookCreation,HookSucceeded'})
        elif kind == 'StatefulSet':
            wave = 8
            document['spec']['persistentVolumeClaimRetentionPolicy'] = {'whenDeleted': 'Retain', 'whenScaled': 'Retain'}
            document['metadata'].setdefault('annotations', {})['argocd.argoproj.io/sync-options'] = 'Prune=false'
        elif kind in ('Deployment', 'CronJob', 'HorizontalPodAutoscaler', 'PodDisruptionBudget'):
            wave = 10
        if kind == 'ConfigMap':
            data = document.get('data', {})
            if any('example.invalid' in text or 'pending-' in text for text in data.values()):
                runtime[name] = data
                # Preserve the full canonical config in Git; hooks write a separate
                # derived ConfigMap, so future chart changes remain visible to Argo.
        if kind in ('Deployment', 'StatefulSet', 'Job', 'CronJob'):
            pod = (document['spec']['jobTemplate']['spec']['template']['spec']
                   if kind == 'CronJob' else document['spec']['template']['spec'])
            pod['automountServiceAccountToken'] = document['metadata']['name'] in (
                'gitlab-shared-secrets', 'gitlab-gitlab-upgrade-check')
            pod.setdefault('securityContext', {})['seccompProfile'] = {'type': 'RuntimeDefault'}
            for container in pod.get('containers', []) + pod.get('initContainers', []):
                image = container['image']
                if image != CLI_IMAGE:
                    container['image'] = image.rsplit(':', 1)[0] + '@' + images[image]
                for env in container.get('env', []):
                    value = env.get('value', '')
                    if isinstance(value, str) and value.startswith('pending-'):
                        key = value.removeprefix('pending-')
                        if key not in runtime['gitlab-runtime-buckets']:
                            raise ValueError('Unexpected bucket environment variable: ' + value)
                        del env['value']
                        env['valueFrom'] = {'configMapKeyRef': {'name': 'gitlab-runtime-buckets', 'key': key}}
        annotate(document, wave)
        result.append(document)
    if release is None or not runtime:
        raise ValueError('Chart no longer produces expected release/runtime configuration')
    for document in result:
        if document['kind'] not in ('Deployment','StatefulSet','Job','CronJob'):
            continue
        pod = (document['spec']['jobTemplate']['spec']['template']['spec']
               if document['kind'] == 'CronJob' else document['spec']['template']['spec'])
        for volume in pod.get('volumes', []):
            ref = volume.get('configMap', {})
            if ref.get('name') in runtime and ref['name'] != 'gitlab-runtime-buckets':
                ref['name'] += '-runtime'
    result.append({'apiVersion': 'v1', 'kind': 'ConfigMap',
                   'metadata': {'name': 'gitlab-runtime-templates', 'namespace': 'gitlab-system',
                                'annotations': {'argocd.argoproj.io/sync-wave': '3'}},
                   'data': {'templates.json': json.dumps(runtime, sort_keys=True),
                            'release.json': json.dumps(release, sort_keys=True)}})
    return result


def sonarqube_documents(documents, images):
    for document in documents:
        if document['kind'] == 'Pod' and 'test' in document['metadata'].get('annotations', {}).get('helm.sh/hook', ''):
            continue
        if document['kind'] in ('SecurityContextConstraints', 'ClusterRoleBinding'):
            raise ValueError('Unexpected chart privilege; SCC/sysctl initialization must stay disabled')
        document['metadata']['namespace'] = 'sonarqube'
        if document['kind'] in ('Deployment', 'StatefulSet', 'Job'):
            pod = document['spec']['template']['spec']
            for container in (pod.get('containers') or []) + (pod.get('initContainers') or []):
                image = container['image']
                container['image'] = image.rsplit(':', 1)[0] + '@' + images[image]
        annotate(document, 10 if document['kind'] == 'StatefulSet' else 6)
        yield document


def chart_archive(entry, directory):
    archive = directory / (entry['name'] + '-chart.tgz')
    if not archive.exists():
        with urllib.request.urlopen(entry['url'], timeout=90) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError('Chart archive checksum mismatch: ' + entry['name'])
    extracted = directory / entry['name']
    # Always extract the verified archive; a modified cache cannot change the render.
    if extracted.exists():
        shutil.rmtree(extracted)
    with tarfile.open(archive) as package:
        for member in package.getmembers():
            if member.issym() or member.islnk() or not member.isfile() and not member.isdir():
                raise ValueError('Unsupported archive member: ' + member.name)
            if directory.resolve() not in (directory / member.name).resolve().parents:
                raise ValueError('Unsafe archive path: ' + member.name)
        package.extractall(directory)
    return extracted


def output_files(documents):
    files = {}
    for document in documents:
        name = document['kind'].lower() + '-' + document['metadata']['name'] + '.yaml'
        if name in files:
            raise ValueError('Duplicate generated resource: ' + name)
        files[name] = '# Generated by scripts/platform/render-stage070-charts.py; edit values/renderer, then regenerate.\n' + dump(document)
    files['kustomization.yaml'] = dump({'apiVersion': 'kustomize.config.k8s.io/v1beta1',
                                      'kind': 'Kustomization', 'resources': sorted(files)})
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Refuse any difference without changing GitOps files')
    parser.add_argument('--cache', type=Path, default=ROOT / 'tmp/stage070-chart-cache')
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    if subprocess.check_output(['helm', 'version', '--template', '{{.Version}}'], text=True) != lock['helm_version']:
        raise ValueError('Render using pinned Helm ' + lock['helm_version'])
    args.cache.mkdir(parents=True, exist_ok=True)
    for entry in lock['charts']:
        chart = chart_archive(entry, args.cache)
        capabilities = [arg for api in lock['api_versions'] for arg in ('--api-versions', api)]
        raw = subprocess.check_output(['helm', 'template', entry['name'], str(chart), '--namespace', entry['namespace'],
            '--kube-version', lock['kubernetes_version'], *capabilities, '--skip-tests', '-f', str(BASE / entry['name'] / 'values.yaml')], text=True)
        documents = [document for document in yaml.safe_load_all(raw) if document]
        documents = (gitlab_documents(documents, lock['gitlab_images']) if entry['name'] == 'gitlab'
                     else sonarqube_documents(documents, lock['sonarqube_images']))
        files = output_files(documents)
        destination = BASE / entry['name'] / 'generated'
        if args.check:
            existing = {path.name: path.read_text() for path in destination.glob('*.yaml')}
            if existing != files:
                changed = sorted(name for name in existing.keys() | files.keys() if existing.get(name) != files.get(name))
                raise ValueError(entry['name'] + ' generated resources are stale: ' + ', '.join(changed))
        else:
            destination.mkdir(exist_ok=True)
            for path in destination.glob('*.yaml'):
                path.unlink()
            for name, contents in files.items():
                (destination / name).write_text(contents)
        print(entry['name'] + ': ' + str(len(files) - 1) + ' Kustomize resources ' + ('verified' if args.check else 'written'))


if __name__ == '__main__':
    main()
