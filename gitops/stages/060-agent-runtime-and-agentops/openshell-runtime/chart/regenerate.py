#!/usr/bin/env python3
"""Reproduce the native Helm resource set; use --check for a non-writing diff."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile
import yaml
p=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chart',required=True,type=pathlib.Path)
parser.add_argument('--check',action='store_true')
a=parser.parse_args()
pins=json.loads((p/'source-pins.json').read_text())
if hashlib.sha256(a.chart.read_bytes()).hexdigest()!=pins['chartArchiveSha256']:
 raise SystemExit('Chart archive differs from the reviewed native OCI layer archive')
env=dict(os.environ,OPENSHELL_CHART_PATH=str(a.chart.resolve()))
render=subprocess.check_output([str(p/'render.sh')],env=env,text=True)
docs=[o for o in yaml.safe_load_all(render) if o]
files={}
for o in docs:
 if o['kind']=='Secret':raise SystemExit('Refusing to publish generated Secret material')
 m=o['metadata'];ns=m.get('namespace','cluster')
 name=f"{o['kind'].lower()}-{ns}-{m['name']}.yaml"
 if name in files:raise SystemExit(f'Duplicate resource identity: {name}')
 files[name]=yaml.safe_dump(o,sort_keys=False)
files['kustomization.yaml']=yaml.safe_dump({'resources':sorted(files)},sort_keys=False)
out=p/'rendered';existing={f.name:f.read_text() for f in out.glob('*.yaml')} if out.exists() else {}
if a.check:
 changed=sorted(k for k in files.keys()|existing.keys() if files.get(k)!=existing.get(k))
 if changed:raise SystemExit('Rendered drift: '+', '.join(changed))
 print(f'Native chart and customer post-render reproduced {len(docs)} resources exactly')
else:
 out.mkdir(exist_ok=True)
 for name in existing.keys()-files.keys():(out/name).unlink()
 for name,content in files.items():(out/name).write_text(content)
 print(f'Wrote {len(docs)} deterministic resource files; no secrets')
