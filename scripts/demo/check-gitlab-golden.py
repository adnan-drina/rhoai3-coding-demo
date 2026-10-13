#!/usr/bin/env python3
"""Compare a private pinned GitLab golden with its checked-in source; no writes."""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {'agentic-quarkus-scaffold': ROOT / 'stages/120-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold',
           'quarkus-migration-scaffold-v2': ROOT / 'stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', choices=list(SOURCES))
    args = parser.parse_args()
    expected = os.environ.get('RHOAI_EXPECTED_API_SERVER', '')
    server = subprocess.check_output(['oc', 'whoami', '--show-server'], text=True).strip()
    if not expected or expected not in server: raise RuntimeError('Cluster guard does not match')
    def oc_json(*args): return json.loads(subprocess.check_output(['oc', *args, '-o', 'json'], text=True))
    config = json.loads(oc_json('get', 'configmap', 'gitlab-platform-config', '-n', 'rhdh')['data']['platform.json'])
    parsed = urlsplit(config[args.name]); project, marker, sha = parsed.path.partition('/-/tree/')
    if parsed.scheme != 'https' or parsed.netloc != config['GITLAB_HOST'] or not marker or not re.fullmatch('[0-9a-f]{40}', sha):
        raise RuntimeError('Golden URL is not pinned to this platform GitLab')
    token = base64.b64decode(oc_json('get', 'secret', 'gitlab-catalog-reader', '-n', 'rhdh')['data']['token']).decode()
    request = urllib.request.Request(config['GITLAB_BASE_URL'] + '/api/v4/projects/' + quote(project.lstrip('/'), safe='') + '/repository/archive.tar.gz?sha=' + sha,
                                     headers={'PRIVATE-TOKEN': token})
    with urllib.request.urlopen(request, timeout=60) as response: data = response.read()
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile(): actual[member.name.partition('/')[2]] = archive.extractfile(member).read()
    source = SOURCES[args.name]
    expected = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts and '.hermes/_park/' not in p.relative_to(source).as_posix()}
    changed = sorted(p for p in set(actual) | set(expected) if actual.get(p) != expected.get(p))
    if changed: raise RuntimeError('Golden differs from checked-in source: ' + ', '.join(changed[:8]))
    print('PASS: ' + args.name + ' at ' + sha + ' matches checked-in source (' + str(len(actual)) + ' files)')


if __name__ == '__main__': main()
