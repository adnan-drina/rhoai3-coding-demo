# Architecture policy in practice

Policy file: `policy/policy.json`. Generator and baseline tool:
`policy/build-policy.py`. Mutation harness: `policy/mutate.py`.
Baseline: `policy/baseline.json`.

Nothing here is copied from the blog. The domains are this application's own package
layout and every threshold decision is made from a number measured on this graph.

## 1. Baseline, measured before any threshold was chosen

Destination graph: 1633 nodes, 4781 edges, 1047 nodes mapped to a domain.

| domain | nodes |
|---|---|
| repository | 361 |
| rest | 297 |
| model | 167 |
| service | 110 |
| mapper | 83 |
| security | 15 |
| util | 14 |

Directed domain crossings actually present:

```
   9  mapper->model [Uses]          28  service->repository [Calls]
  14  repository->model [Calls]      7  service->repository [Uses]
   6  repository->model [References] 5  service->model [Calls]
  78  repository->model [Uses]      15  service->model [Uses]
  34  rest->mapper [Calls]           1  service->util [Uses]
   8  rest->mapper [Uses]            1  util->model [Calls]
  40  rest->model [Calls]            1  util->model [Uses]
   8  rest->model [Uses]
   7  rest->service [Uses]
```

Centrality: max betweenness **6.35e-5**. Impact: max `impact_zone_size` **19**
(`BaseEntity.getId`); 189 of 291 application functions report **0**.

## 2. The rules chosen, and the ones deliberately not chosen

**Chosen, blocking: `forbidden_crossings: [["rest","repository"]]`.**
The undesirable relationship it prevents is concrete and this application's own:
`ClinicService` is documented in the source as "a facade so all controllers have a
single point of entry", and ADR-012's fragment adapters now sit behind it. A
controller that reaches a repository directly bypasses both the facade and the
transaction boundary the service layer owns, and would make the adapters' behaviour
reachable by two different paths. The baseline shows **zero** such edges today, so
the rule is satisfied on a clean tree and any violation would be introduced, not
pre-existing.

**Not chosen: `max_impact_nodes`.** Measured maximum is 19, and the distribution is
dominated by 189 zeros produced by unresolved interface dispatch (FINDINGS F-5), not
by genuine isolation. A threshold above 19 is inert; one below it fires on a getter.
It would measure the resolver, not the architecture.

**Not chosen: `centrality_alert_threshold`.** Measured maximum betweenness is
6.35e-5. The blog's 0.8 is four orders of magnitude away from anything this graph
produces; adopting it would be a rule that can never fire.

**Pre-existing violations: none.** All violations discussed below are introduced.

## 3. The mutation test

A temporary violating change was added to one controller — a directly injected
`VetRepository` field and a method calling it — and a passing counterpart doing the
same work through `clinicService`. Both were removed afterwards; the application
tree is clean (`git status` empty at commit `b34e3ea`).

| step | graph state | `check` result |
|---|---|---|
| clean tree | fresh | `passed: true`, 0 violations |
| violating change, **graph not re-indexed** | stale | `passed: true`, 0 violations |
| violating change, graph re-indexed, **original policy** | fresh | `passed: true`, 0 violations |
| violating change, graph re-indexed, **policy rebuilt** | fresh | `passed: true`, 0 violations |
| passing counterpart, graph re-indexed, policy rebuilt | fresh | `passed: true`, 0 violations |

Every row passes. The violating change and its legitimate counterpart are
indistinguishable to the gate.

## 4. The operational questions, answered

**Does `check` evaluate changed files or the whole graph, in this version and git
state?** It evaluated against the persisted graph, which predated the edit. `git
status` showed the file modified; `check` reported `passed: true`. Nothing in the
output says the graph is stale. **The gate is blind to the change it exists to gate
unless `discover` is re-run first, and it does not say so.**

**Does the graph reflect the candidate being checked?** Only if you re-index by hand,
and re-indexing has the consequence below.

**Do domain mappings remain valid after rediscovery?** No — and this is the decisive
finding. After one `rgctl discover`, **0 of 1047** policy `node_domains` UUIDs still
existed in the graph. Node ids are regenerated on every index. A policy file keyed by
UUID is therefore invalidated by the very command that must precede the check. Worse:
an invalidated policy does not error. It passes, with `violations: []`, exactly like a
policy that found nothing wrong. A committed policy file is a false green from the
second index onward.

**Does a forbidden crossing also reject a legitimate dependency in the opposite
direction?** Not answerable on this codebase, because the crossing never fired in
either direction. The reason is more serious than the question: inspecting the fresh
export after the violating change, the graph contains **zero** edges between
`VetRestController` and anything under `repository/`, in either direction — although
it did index the new method and the new field. The forbidden relationship exists in
the source, compiles, and would run; it is simply not an edge. Given the
direction inconsistency in FINDINGS F-4, a crossing rule that did fire could not be
trusted to fire on the right side either.

## 5. Verdict

The policy engine's mechanics work: the schema is simple, `check` is fast, exit codes
are usable in CI. The trouble is entirely upstream of it.

- On this application it **caught nothing**, because the relationships it forbids are
  not in the graph.
- It **passes silently** in two distinct failure modes — a stale graph, and a policy
  whose node ids no longer exist — and both look identical to a genuine pass.
- The one thing it produced that I would keep is the **baseline measurement**, not the
  gate: knowing that `rest -> repository` has zero edges, and seeing the full crossing
  table, is a useful architectural readout of a migrated tree.

A gate that cannot distinguish "nothing is wrong" from "I am looking at the wrong
graph" or "my identifiers all expired" is the failure mode this programme has been
burned by before. I would not put this in the loop as a blocking check.
