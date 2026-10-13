#!/usr/bin/env python3
"""Stage verified MTA artifacts without redistributing the download in Git."""
import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'stages/070-advanced-app-platform/workspace-image'


def verify(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('Artifact checksum mismatch: ' + path.name)


def prepare(archive, out):
    lock = json.loads((SOURCE / 'artifacts.lock.json').read_text())
    verify(archive, lock['mta_cli']['archive_sha256'])
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(SOURCE / 'Dockerfile', out / 'Dockerfile')
    cli = out / 'mta-cli'
    if cli.exists(): shutil.rmtree(cli)
    cli.mkdir()
    with zipfile.ZipFile(archive) as zip_:
        for member in zip_.infolist():
            target = (cli / member.filename).resolve()
            if not target.is_relative_to(cli.resolve()):
                raise ValueError('Archive path escapes its install prefix')
        zip_.extractall(cli)
        for member in zip_.infolist():
            path = cli / member.filename
            if path.is_file(): path.chmod((member.external_attr >> 16) & 0o777 or 0o644)
    verify(cli / lock['mta_cli']['binary_path'], lock['mta_cli']['binary_sha256'])
    extensions = out / 'extensions'
    extensions.mkdir(exist_ok=True)
    for row in lock['extensions']:
        path = extensions / (row['name'] + '.vsix')
        if not path.exists(): urllib.request.urlretrieve(row['url'], path)
        verify(path, row['sha256'])
    (out / 'artifacts.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    print('Verified MTA CLI and all four required editor extensions: ' + str(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mta-archive', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    prepare(args.mta_archive, args.out)
