# O-EXECCORPUS — execution replay fixtures

Symmetric with `plan-corpus/`: archived v3 S03 execution artifacts replayed
against today's supervisor honesty predicates (sfix skip, escalation cause).

## Extract path (host)

Primary scoop (before PVC reclaim):

- `tmp/s03-clean-stop-20260803T052227Z/s03-run-archives.tgz`
  → `20260803T052227Z-clean-stop-s03/{oc-*.json,.err,failure-sig-*,escalation-cause-*,supervisor.log,…}`
- `tmp/s03-clean-stop-20260803T052227Z/files/` (unpacked twin)
- Seat index: `tmp/run-archives/S03-20260803/s03-seat-corpus.tgz`

Cases under this tree keep **small** slices (excerpts / failure-sigs / cause
files). Full `oc-*.json` bodies stay in the host tarballs — see each case
`SOURCE.txt`. Re-extract with:

```bash
mkdir -p /tmp/execcorpus-extract
tar xzf tmp/s03-clean-stop-20260803T052227Z/s03-run-archives.tgz -C /tmp/execcorpus-extract
```

## Run

```bash
bash .hermes/harness/exec-corpus-lint.sh
bash .hermes/harness/exec-corpus-lint.sh --case s03-t004-sfixnodelta
```
