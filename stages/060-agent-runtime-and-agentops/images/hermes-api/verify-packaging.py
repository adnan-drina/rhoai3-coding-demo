"""Build-time proof that packaging preserves the selected fork and existing packages."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

root = Path('/opt/rhoai3/hermes-api')
source = json.loads((root / 'dependency-source.json').read_text())
stamp = Path('/opt/rhoai3/080.pins').read_bytes()
assert source['hermesSourceCommit'].encode() in stamp and source['hermesPatchedTree'].encode() in stamp
versions = {d.metadata['Name'].lower().replace('_', '-'): d.version for d in metadata.distributions()}
baseline = Path('/tmp/hermes-api-before.json')
if sys.argv[1] == 'before':
    for name, version in source['existingUnchanged'].items():
        assert versions[name.replace('_', '-')] == version
    baseline.write_text(json.dumps({'versions': versions, 'stampSha256': hashlib.sha256(stamp).hexdigest()}))
else:
    before = json.loads(baseline.read_text())
    assert hashlib.sha256(stamp).hexdigest() == before['stampSha256']
    assert all(versions.get(name) == version for name, version in before['versions'].items()), 'Existing distribution changed'
    expected = {w['name'].lower().replace('_', '-'): w['version'] for w in source['wheels']}
    assert all(versions.get(name) == version for name, version in expected.items())
    assert set(versions) - set(before['versions']) == set(expected) - set(before['versions']), 'Unreviewed distribution added'
    import aiohttp
    from gateway.platforms.api_server import AIOHTTP_AVAILABLE
    assert AIOHTTP_AVAILABLE and aiohttp.__version__ == '3.14.3'
    (root / 'packaging-evidence.json').write_text(json.dumps({'baseImage': source['baseImage'], 'hermesSourceCommit': source['hermesSourceCommit'], 'hermesPatchedTree': source['hermesPatchedTree'], 'baseStampSha256': before['stampSha256'], 'newDistributions': sorted(set(versions) - set(before['versions'])), 'requirementsSha256': hashlib.sha256((root / 'requirements.lock').read_bytes()).hexdigest()}))
