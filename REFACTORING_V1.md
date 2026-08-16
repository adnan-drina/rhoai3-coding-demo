
## E-20260816T184454Z — 2026-08-16T18:44:54Z — decide — **OPERATOR DOCTRINE: the harness is PROVISIONED, never patched. Stop → harvest → fix in golden → publish → wipe → restart. Two traps found: the gate strip is uncommitted, and the published golden predates it.** — Operator (via Deputy)

**Needs:** Lead:harvest-attempt1-before-wipe(E-20260816T184454Z) — **HARD, IRREVERSIBLE IF SKIPPED: do before any wipe**, Lead:land-and-publish-golden-before-reprovision(E-20260816T184454Z) — **HARD: commit ≠ publish; a reprovision today restores the `type: gate` steps**, Architect:absorb-provision-not-patch-doctrine(E-20260816T184454Z) — supersedes the (a)/(b) fork in `E-20260816T184009Z`
**Done:** Architect:rule-attempt1-m3-or-cut(E-20260816T184009Z) — WITHDRAWN (Operator ruled the frame, not the branch)
**Re:** E-20260816T184009Z, E-20260816T182206Z, E-20260816T175500Z, E-20260816T175250Z, tmp/LEAD-COMMISSION-V20-BUILD.md Phase 5

### The ruling

> **Operator, 2026-08-16:** *"When we need to apply a mid-run harness patch, we can stop
> the run, wipe it out from the workspace, implement the fix, and restart the run."*

**This is doctrine, not a disposition of one fork.** It dissolves
`E-20260816T184009Z` rather than answering it: if the harness is provisioned and never
patched, **branch (a) does not exist**. My recommendation there — *"attempt 1's number
is already unrecoverable, so purity buys nothing"* — was optimising inside a frame that
permitted mid-run patching. **The Operator's rule is stronger and I withdraw (a).**

**No evidence is lost by it.** A clean provision yields the M3 machinery evidence
(`handover-mint.py`, B-1 on real code, B-2 on real source, worktrees,
remediation-on-REFUSE) **and** a valid intervention count, for ~25 min of recompute
(measured today: M1 16:51–16:56, M2 17:50–18:19; the rest of the day was rulings).

**Retroactive consequence — name it:** today's overlay strip (`175220Z`), daemon stop
(`182109Z`) and env-var route around the write fence (`180000Z`) are all **the same
category**: live repairs to a provisioned harness. Under this doctrine each would have
been a stop-and-restart. **That is what makes an attempt reproducible from a published
SHA instead of from a sequence of undocumented repairs** — the factory-settings
doctrine of 2026-08-07, finally stated as an operating rule.

### TRAP 1 — the gate strip is uncommitted, and the published golden predates it

**Verified at HEAD just now:**

| Fact | State |
|---|---|
| `stop-before-implement.overlay.yml` carries `remove: review-spec` + `remove: review-plan` | **YES** — and the file is an **uncommitted working-tree modification** |
| Platform commits since `9ab66c6c` | only `f7c1f086`, `cf93292e` — **neither is the overlay** |
| Published golden the provisioner reads | **`27dd2b01`, cut from `9ab66c6c` @ 15:12:24Z** (`tmp/v20-run/PREFLIGHT.md`) — **predates the strip** |

**Therefore a wipe-and-reprovision today restores both `type: gate` steps**, and the
first symptom would be M2 hitting a gate again — after the cause had been diagnosed,
ruled on, and believed fixed. **Commit is not publish.** Publishing is the step that
otherwise silently undoes the fix batch.

### TRAP 2 — harvest before wipe; attempt 1's output exists only on the PVC

Review's packs are safe in `monitoring/v20/`. **Nothing below is.**

- `specs/` — `tasks.md` **19565 B**, `spec.md` 8718, `plan.md` 6838, `research.md` 5616,
  `data-model.md` 4064, `quickstart.md` 1978, `contracts/`, `checklists/`
- `evidence/` — `mta-findings.json` **336885 B**, `findings-handoff.json`,
  `entry-point-inventory.json`, `mta/rules-coverage.json`, `derived/legacy-at-3.json`,
  `derived/m1-findings-digest.json`, `acks/m1-findings.ack.yaml`
- **kanban DB + worker transcripts** — the **only** source for any census recomputation
  (claim windows, `task_runs`, comments, `skill_view` counts). Lost with the PVC.

Land under `harness-refactoring/monitoring/v20/attempt-1/`. The run is terminal (both
cards `done`), so harvest reads cannot contaminate anything.

### The restart sequence

1. **Harvest** the above off the PVC.
2. **Land every fix in golden, committed** — overlay strip (uncommitted now) · run-audit
   card-boundary caller + `_is_dest_path` widened beyond `pom.xml`+`src/` · `.specify/`
   vs `specs/` write-set decision (AD-013: do not make the native tool route around the
   fence) · whatever spawned `--force` on M1 dispatch · ack-checker YAML scrape
   (`173510Z` — every Operator ack walks that path).
3. `validate-contracts` **PASS at HEAD; working tree clean.**
4. **Re-publish golden** → new published SHA. **This is the step that is easy to skip.**
5. **Then** wipe the workspace and reprovision from that SHA.
6. **`t0` before the first card**; daemon confirmed absent; then M1.

Attempt 2 is the **scored** run: `t0` from provision, gates stripped in golden, write-set
decided, audit armed — no live repairs permitted. If one becomes necessary, **stop and
restart**; that is now the rule, not a judgement call.

### Attempt 1 — what it bought

Not nothing. **`skill_view` 0 → non-zero** (`speckit-plan`, `speckit-tasks`);
**`specify` CLI 0 → a live workflow run**; the full native chain executed to `tasks.md`;
`review-spec`/`review-plan` **measured** as `type: gate` (closing a question argued from
text all day); the write-fence/spec-kit conflict surfaced; the run-audit include-gate
defect found. **Intervention count: NOT MEASURED — never a silent 0.**

No dest access for this entry; read from the ledger and golden at HEAD. No secrets.

— Operator (via Deputy)
