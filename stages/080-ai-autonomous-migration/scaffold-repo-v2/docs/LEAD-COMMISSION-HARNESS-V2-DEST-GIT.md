# Lead commission — dest git `greeting-v2` + keep v2 work on `harness-v2`

**From:** Architect · **To:** Lead · **Date:** 2026-08-21 · **Cite:** AD-019, Operator GO dest-git (Architect session), Operator `E-20260821T124605Z`
**Not dest provision.** No Dev Spaces, no RHDH template, no Argo, no v42 overlay.

Waives Lead’s standing OBJECT `gh repo create` **only** for the named repo below. The V34-P3 “do not gh repo create” rule was for v1 dests that the `app-migration` template publishes. v2 must **not** use that template (it still clones v1 `quarkus-migration-scaffold`).

---

## Why Lead, not Architect

Architect already created local branch `harness-v2` @ `170ce41c` (empty `scaffold-repo-v2/`). Pushing a GitHub dest and moving the campaign off `overlay-a8-publish` is Lead land.

Lead relay is **DEAD** (`.wake/lead-relay-DEAD`). Execute from this file; do not wait on wake.

---

## Clean-slate rules (lint these; they are BIND)

1. **v2 code lives only under** `stages/080-ai-autonomous-migration/scaffold-repo-v2/`. A v2 commit that touches `scaffold-repo/` (no `-v2`) is a mistake.
2. **`overlay-a8-publish` takes no new v1 harness commits** after the current tag, **except v42 harvest** (capture, not development).
3. **v42 is ephemeral.** Harvest before wipe (**HV-1**). Do not wipe v42 in this card.
4. **Bootstrap a v2 golden only when v2 is ready to provision**, and to a **separate** repo name (`quarkus-migration-scaffold-v2`). **Never** `scripts/bootstrap-scaffold-repos.sh` (that force-pushes v1 `quarkus-migration-scaffold`).

---

## Card A — `Lead:push-harness-v2`

```bash
cd /Users/adrina/Sandbox/rhoai3-coding-demo
git fetch origin
git log -1 --oneline harness-v2
# expected: 170ce41c or a child that only adds scaffold-repo-v2/
git push -u origin harness-v2
```

Do **not** merge into `overlay-a8-publish`. Do **not** push WIP on overlay (kanban-log-watch, maas-api-key-provisioning, etc.).

Exit: `origin/harness-v2` exists; `git merge-base --is-ancestor 1c2664e4 origin/harness-v2`.

---

## Card B — `Lead:create-dest-git-greeting-v2`

Create **GitHub dest repo only**. No cluster.

```bash
# Refuse if it already exists — do not force-push over someone else's dest
gh repo view adnan-drina/greeting-v2 && echo REFUSE: exists && exit 1

ROOT=/Users/adrina/Sandbox/rhoai3-coding-demo
SRC="$ROOT/stages/080-ai-autonomous-migration/scaffold-repo-v2/quarkus-migration-scaffold"
test -f "$SRC/.hermes/pins.json" || { echo REFUSE: checkout harness-v2 first; exit 1; }

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
cp -R "$SRC/." "$WORKDIR/"
# do not copy v1 scaffold-repo/

cd "$WORKDIR"
git init -b main
git add -A
git commit -m "$(cat <<'EOF'
Initial greeting-v2 dest from harness-v2 empty golden (AD-019). Not provisioned.

EOF
)"

gh repo create adnan-drina/greeting-v2 --public \
  --description "harness-v2 destination (AD-019). Empty pins+config stub. Do not point app-migration at this until Operator GO. Not v1 golden." \
  --source . --remote origin --push
```

**Topics — HARD off:** do **not** add `rhoai3-scaffolded` (Argo bootstrap) or `rhoai3-golden-path` (v1 golden reset). No webhook on this repo until provision GO.

**OBJECT:** `bootstrap-scaffold-repos.sh`; force-push to `quarkus-migration-scaffold`; `oc apply` DevWorkspace; RHDH Self-service `app-migration` with name `greeting-v2` (would try to publish **v1** golden into this name); dest-complete; dest-read `.env`; `kanban daemon --force`.

Exit: `gh repo view adnan-drina/greeting-v2 --json url,defaultBranchRef` shows `main`; clone contains `.hermes/pins.json` + `.hermes/config.yaml`; topics empty or not the two forbidden names.

---

## Card C — `Lead:harvest-v42-before-wipe` (HV-1)

**Not this turn.** HARD before any v42 wipe. Capture board + `HARNESS_REV` + JAVA_SRC + official logs. v42 stays live until Operator names wipe.

---

## File after

Ledger hop: dest git URL, `origin/harness-v2` SHA, confirmation topics are absent. `Needs:` none dest-provision.

— Architect
