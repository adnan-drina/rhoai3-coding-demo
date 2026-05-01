---
name: workaround-review
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
description: >
  Review and manage workaround status when touching known RHOAI, MaaS, gateway,
  GPU, or Dev Spaces workarounds. Use when modifying code that implements a
  documented workaround, when checking if a workaround is still needed, or when
  adding a new workaround. Do NOT use for general troubleshooting (use
  rhoai-troubleshoot), manifest review (use review-gitops-change), or
  documentation updates (use update-demo-docs).
---

# Workaround Review

Use this skill when touching code or configuration related to known platform
workarounds, or when evaluating whether a workaround can be removed.

## When to invoke

- Modifying files that implement a documented workaround
- Upgrading RHOAI, MaaS, or operator versions
- A user asks "can we remove this workaround?"
- Adding a new temporary workaround
- Reviewing BACKLOG.md for staleness

## Inputs needed

- The workaround in question (file paths or BACKLOG.md entry)
- Current platform versions (check `00-demo-doc-first.mdc` for targets)
- Whether a live cluster is available for testing

## Review workflow

### 1. Identify the workaround

Read `BACKLOG.md` to find:
- What the workaround does
- Why it exists (which platform gap)
- What files implement it
- When it can be removed (removal condition)

### 2. Check if still needed

For RHOAI version-dependent workarounds:
- What version is currently deployed? (`oc get csv -n redhat-ods-operator`)
- Does the new version address the gap?
- Is there official documentation confirming the fix?

For upstream maas-controller workarounds:
- Has the RHOAI operator absorbed the functionality?
- Is the upstream component still required?

### 3. Validate before removal

If a workaround appears removable:

```bash
# Check current platform state
oc get csv -n redhat-ods-operator | grep rhods
oc get datasciencecluster -A

# For MaaS workarounds
oc get gateway -n maas
oc get authpolicy -n maas
oc get inferenceservice -n maas

# For gateway workarounds
oc get httproute -n maas
oc get envoyfilter -n maas
```

Do NOT remove a workaround based on documentation alone. Verify on the live
cluster that the platform now handles the behavior natively.

### 4. Document the decision

If keeping the workaround:
- Confirm the entry in `BACKLOG.md` is still accurate
- Update the removal condition if the timeline changed

If removing the workaround:
- Move the `BACKLOG.md` entry to the Completed section with date and evidence
- Remove the implementing code
- Update `docs/TROUBLESHOOTING.md` if it references the workaround
- Update any stage README that mentions the workaround behavior

If adding a new workaround:
- Add entry to `BACKLOG.md` under the appropriate section
- Include: what it does, why, affected files, removal condition
- Add comments in the implementing code referencing `BACKLOG.md`
- Update `docs/TROUBLESHOOTING.md` if users might hit the underlying issue

## Output format

```markdown
## Workaround review

### Workaround
[Name from BACKLOG.md]

### Status
[Still needed / Can be removed / Needs investigation]

### Evidence
[What was checked — commands run, docs consulted, versions verified]

### BACKLOG.md update needed
[Yes/No — describe the update]

### Code changes needed
[Files to modify or remove, or "None"]

### Documentation changes needed
[TROUBLESHOOTING.md, README, or "None"]

### Risk if removed prematurely
[What would break]
```

## Current workaround categories

From `BACKLOG.md`:

| Category | Examples |
|----------|----------|
| RHOAI 3.3 → 3.4 GA | AuthPolicy patches, Authorino SSL, gateway hostname, tier-to-group ConfigMap |
| Upstream maas-controller | maas-api image pinning, models-as-a-service namespace, tokens-bridge |
| Known limitations | ExternalModel naming, AI asset endpoints dropdown, /v1/responses support |

## What this skill must never do

- Remove a workaround without live cluster verification
- Delete BACKLOG.md history (move to Completed, don't delete)
- Assume a platform gap is fixed based on release notes alone
- Modify workaround code without checking downstream impact
