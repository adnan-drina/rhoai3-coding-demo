#!/bin/bash
# Uncapped javac diagnostic census for the destination tree. Usage: diag.sh <tag>
A=/Users/adrina/Sandbox/rgctl-experiment/app
L=/Users/adrina/Sandbox/rgctl-experiment/_evidence
TAG=${1:-now}
mkdir -p $L
cd $A
find $A/src/main/java $A/target/generated-sources -name '*.java' 2>/dev/null > $L/srcs.txt
rm -rf /tmp/jcout-$TAG; mkdir -p /tmp/jcout-$TAG
javac -proc:none -nowarn -d /tmp/jcout-$TAG -Xmaxerrs 100000 --release 21 -cp "$(cat $L/cp.txt)" @$L/srcs.txt > $L/javac-$TAG.log 2>&1
python3 - "$L/javac-$TAG.log" "$TAG" <<'PY'
import re,sys,collections
ls=open(sys.argv[1]).read().splitlines()
errs=[]
for i,ln in enumerate(ls):
    m=re.match(r'^(/.*?\.java):(\d+): error: (.*)$', ln)
    if m:
        sym=None
        for j in (i+1,i+2,i+3):
            if j<len(ls) and 'symbol:' in ls[j]: sym=ls[j].split('symbol:')[1].strip(); break
        errs.append((m.group(1).split('petclinic/')[-1], m.group(3), sym))
print(f"[{sys.argv[2]}] TOTAL DIAGNOSTICS: {len(errs)}")
print("-- by file --")
for f,n in collections.Counter(e[0] for e in errs).most_common(40): print(f"  {n:4d}  {f}")
print("-- by symbol --")
for s,n in collections.Counter(e[2] for e in errs if e[2]).most_common(30): print(f"  {n:4d}  {s}")
print("-- by message --")
for s,n in collections.Counter(e[1] for e in errs if 'cannot find symbol' not in e[1]).most_common(20): print(f"  {n:4d}  {s[:100]}")
PY
