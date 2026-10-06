#!/usr/bin/env bash
# Original measured-usage export; not a native dashboard CSV or billing integration.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../scripts/shared/lib.sh"
load_env >&2
check_oc_logged_in >&2
oc --request-timeout=10s auth can-i create pods/portforward -n redhat-ods-monitoring | grep -qx yes || { echo 'ERROR: monitoring tunnel authorization required' >&2;exit 1; }
python3 - "$SCRIPT_DIR/showback-ratecard.json" "$@" <<'PYTHON'
import argparse,csv,datetime,json,math,os,pathlib,socket,subprocess,sys,time,urllib.error,urllib.parse,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
parser=argparse.ArgumentParser(description='Export measured MaaS usage without financial prices or content capture.')
parser.add_argument('--from',dest='start',required=True,help='UTC RFC3339, e.g. 2026-10-06T00:00:00Z')
parser.add_argument('--to',dest='end',required=True)
parser.add_argument('--output',required=True,help='Private local CSV path; never commit identity-bearing reports.')
a=parser.parse_args(sys.argv[2:])
def timestamp(s):
    d=datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None or d.utcoffset()!=datetime.timedelta(0):raise ValueError('UTC timestamps required')
    return d.timestamp()
start,end=timestamp(a.start),timestamp(a.end);seconds=int(end-start)
if seconds<60 or seconds>89*86400 or start<time.time()-89*86400 or end>time.time()+60:raise ValueError('Window must be 1 minute to 89 days, within native 90-day retention and not future')
ratecard=json.loads(pathlib.Path(sys.argv[1]).read_text())
if ratecard.get('pricing_status')!='unpriced' or ratecard.get('currency') is not None or ratecard.get('rates')!={}:raise ValueError('Only the reviewed unpriced ratecard is supported')
output=pathlib.Path(a.output).resolve()
if output.exists():raise ValueError('Output already exists; preserve earlier report')
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
p=subprocess.Popen(['oc','-n','redhat-ods-monitoring','port-forward','service/thanos-querier-data-science-thanos-querier',f'{port}:10902'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
rows=[];coverage={};opener=urllib.request.build_opener(NoRedirect)
try:
    for _ in range(30):
        if p.poll() is not None:raise RuntimeError('Native monitoring tunnel failed')
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Native monitoring tunnel timed out')
    dimensions='user,subscription,model,cost_center,organization_id,limitador_namespace'
    for metric,category in [('authorized_hits_total','governed_total_tokens'),('authorized_calls_total','authorized_calls'),('limited_calls_total','limited_calls')]:
        # Read underlying resource series before aggregation; never join calls to multiple models.
        query=f'increase({metric}{{user!="",subscription!=""}}[{seconds}s] @ {int(end)})'
        url=f'http://127.0.0.1:{port}/api/v1/query?'+urllib.parse.urlencode({'query':query,'dedup':'true'})
        with opener.open(url,timeout=20) as response:data=json.loads(response.read(4*1024*1024))
        if data.get('status')!='success':raise RuntimeError('Native usage query failed')
        values=data.get('data',{}).get('result',[]);coverage[category]='observed' if values else 'unknown/no attributed series'
        seen=set()
        for value in values:
            n=float(value['value'][1])
            if not math.isfinite(n) or n<0:raise RuntimeError('Invalid native usage value')
            labels=value.get('metric',{})
            key=tuple(labels.get(k,'') for k in dimensions.split(','))
            if not labels.get('user') or not labels.get('subscription') or key in seen:raise RuntimeError('Missing attribution or duplicate aggregate series')
            seen.add(key)
            rows.append({'window_start_utc':a.start,'window_end_utc':a.end,'category':category,'user':labels.get('user',''),'subscription':labels.get('subscription',''),'model':labels.get('model',''),'cost_center':labels.get('cost_center',''),'organization_id':labels.get('organization_id',''),'limiter_resource':labels.get('limitador_namespace',''),'measured_quantity':n,'input_tokens':'unknown','output_tokens':'unknown','pricing_status':'unpriced','currency':'','estimated_cost':'','coverage':'observed series; Prometheus increase estimate'})
    fields=['window_start_utc','window_end_utc','category','user','subscription','model','cost_center','organization_id','limiter_resource','measured_quantity','input_tokens','output_tokens','pricing_status','currency','estimated_cost','coverage']
    output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    receipt=output.with_suffix(output.suffix+'.json')
    if receipt.exists():raise ValueError('Receipt already exists')
    with os.fdopen(os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
        json.dump({'source':'native RHOAI Thanos via authorized local tunnel','window':{'from':a.start,'to':a.end},'coverage':coverage,'rows':len(rows),'pricing_status':'unpriced','limitations':['No input/output token split','No MCP/agent trajectory accounting','No GPU fixed-cost allocation','Counter sampling/reset/retention can affect estimates','Rows remain scoped to native limiter resources; overlapping policies must not be summed','Duplicate underlying semantic resource series are rejected before aggregation','Absent categories are unknown, not zero','Not billing-grade or provider invoice reconciliation']},f,indent=2)
    print(f'Exported {len(rows)} measured usage rows; financial amounts remain unpriced. Coverage receipt: {receipt}')
finally:
    p.terminate()
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
PYTHON
