---
name: ensure-cli-capability
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/mta-analyze-legacy.sh
  - stages/080-ai-autonomous-migration/scaffold-repo/**/assert-ensure-cli-path.sh
  - gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml
---

# ensure_cli is a capability probe, not a presence probe

`ensure_cli` in the Stage 080 golden analyzer must not `return 0` on the first
path that `[ -x ]` / `command -v` finds. A present `kantra` next to a
non-executable `java-external-provider` (or jdtls launcher) is unusable: M1
dies three layers later, and dest-3 showed a worker encoding paths to `chmod`
an overlay tree it cannot repair.

Operator design: `E-20260825T062531ZO`. Architect BIND: `E-20260825T062943ZA`,
amended `E-20260825T070220ZO` (ELF **or shebang**; group-exec for uid≠owner
in gid 0). Do not dest-push dest-3’s worker-patched analyzer as golden.

## Non-negotiable

1. After **each** resolved CLI path, run dest-init `kantra-assert-exec` on the
   **install prefix** (resolved realpath directory of the binary, so a
   `/usr/local/bin/kantra` symlink into `/opt/kantra` asserts `/opt/kantra`,
   not `/usr/local/bin`).
2. Failure **falls through** to the next probe (eventually PVC
   `kantra-ensure`). Never treat present-but-unusable overlay kantra as
   success. Overlay `/opt/kantra` is `chown 10001:0`; the dest user cannot
   chmod it — that is why fall-through exists.
3. Reuse `~/.local/bin/kantra-assert-exec`. Do not reimplement ELF/shebang
   lists or a name whitelist in the skill. Research `E-20260825T073015ZS`
   (mta-cli skill + official MTA 8.2): there is **no** documented version,
   RPC, or KAI handshake as a usability gate. Do **not** add `kantra version`
   or provider RPC probes. The property check stays because we measured
   zipfile mode-loss, not because official requires it.
4. `CLI="$(ensure_cli)"` still captures **one** path on stdout. Checker chatter
   stays on stderr. Extend `assert-ensure-cli-path.sh` so a tree with a
   non-executable sibling is **not** accepted.
5. Land in golden `mta-analyze-legacy.sh` + `scan-with-mta/SKILL.md` procedure
   step 1, then `bootstrap-migration-scaffold-v2.sh`. Not a dest-4 cut
   blocker. Do not dest-exec `kantra-assert-exec` on dest-3 `/opt/kantra` as
   MATCH.

Campaign law: nested AD-019 lesson 17. Checker source:
`gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml`
(`kantra-assert-exec`).
