# Grounded code generation (IMPLEMENT)

**Status:** binding for migration workspace · mirrors **AD-H §17**  
**Sources:** Architect plan / AD-H §17 (Operator ACK `E-20260808T072759Z`)  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

Applies to the **implementer** role (M3). SOUL / AD-S §S.6 / AD-H §16 /
pattern-steals / G-1…G-4 stand. Higher-priority sources win on conflict; lower
sources may only supply *expression*, never new *behaviour*.

## Consult order (priority high → low)

| Pri | Source | Owns | May not |
|-----|--------|------|---------|
| **1** | **Approved task packet** (`ac_ids`, `files_in_scope`, deps, inlined facts) | Hard scope fence | Expand paths or ACs |
| **2** | **Approved brief/spec identity** (acked per AD-H §16) | What/why, Non-Goals, ACs | Invent features; drop Non-Goals |
| **3** | **Current legacy code** (RO; prefer packet-anchored excerpts; `legacy-at-3` / staged harvest when packet says so) | Behavioural truth (SOUL) | Edit; invent absent behaviour |
| **4** | **Target reference implementation** | Accepted destination code + `AGENTS.md` / constitution | Copy unrelated modules; override legacy |
| **5** | **Approved Quarkus documentation** (allowlist below) | Framework *how* | New business rules, DB shape, integration behaviour |

**Pri-5 allowlist** (Research AMEND `E-20260808T074430Z`): (1) Quarkus docs
matching RH BOM / destination version (demo default **3.27**); (2) scaffold
skills / free-primitives `RULES.md` / related skill refs; (3) optional
quarkusio Full-path materials already cited by those skills. **Out:** unlisted
blogs, unmatched quarkus.io pages, arbitrary web hits.

**Conflict rule:** legacy behaviour + brief identity beat docs and destination
patterns. MTA findings are evidence of work, not authority to invent APIs.
Open `Q-*` → stop; do not guess.

## Citation required

Every **non-trivial** generated change must cite in the commit message and/or
task completion metadata:

1. **Task id** (AD-H §7.5)
2. **Brief / story id** (or spec path + identity ACK ref)
3. **Legacy locus** — path + line range (or staging/harvest path the packet asserts)

**Non-trivial** = behaviour, API/SPI, persistence, config semantics, integration,
or tests asserting behaviour.

**Trivial exemption** (task id only): formatting, import order, or mechanical
rename inside `files_in_scope` with no semantic change — still sensor-gated.

Missing citation → refuse or Kanban `blocked`.

## What prevents invention

| Layer | Control |
|-------|---------|
| Identity | Non-Goals + ACs; open `Q-*` blocks readiness |
| Scope | `files_in_scope` + SOUL stop; no IMPLEMENT re-plan |
| Packet facts | Anchored excerpts in `body` |
| Class | HARVEST from staged/recipe only; REDESIGN from `targetContract` / AC only |
| Gates | G-1…G-4 — ACCEPT needs oracle |
| Process | Invention → `blocked`, not improvise |
| Human | Brief/spec ACK before first IMPLEMENT; `mta-exception` + `re_open_trigger` |

Citation lints do **not** replace domain-gate oracles.

## Enforcement (Lead)

| Piece | Path |
|-------|------|
| Citation + invent-without-locus | `.hermes/skills/grounded-generation/scripts/check-citation.py` |
| Wired into | `harness-validate`; M3 `skills[]` in `phase-dispatch.yaml` |

```bash
python3 .hermes/skills/grounded-generation/scripts/check-citation.py .
python3 .hermes/skills/grounded-generation/scripts/check-citation.py . --commit-msg MSGFILE
```

Non-blocking vs open Review / deferred items. Citation lints do **not** replace
domain-gate oracles.
