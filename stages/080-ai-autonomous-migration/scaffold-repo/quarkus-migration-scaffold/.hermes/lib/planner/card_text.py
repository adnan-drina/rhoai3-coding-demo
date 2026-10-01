"""Human-readable card text for the native board: titles, descriptions and
review handoffs rendered from the plan's semantic facts (H-11 slice 1,
v30 Kanban readability review 2026-10-01).

What a person (or a worker) reading a card must be able to answer: what is
this card for, what proves it is done, what is checked later by someone else,
why does it exist (a follow-up), and -- at handoff -- what passed, what failed
and what was not measured. The v30 bodies said "0 owned obligations" on cards
that owned a generator check and 28 later checks, titled objectives "Make
implement ...", and handed off check CLASSES ("checks build, compile") instead
of results.

Deterministic, specimen-agnostic: every phrase is derived from the structured
facts (requirement rule + subject, the node's acceptance, acceptance_states,
schedule, lineage, plan paths). Nothing is summarized by a model, no business
meaning is invented from an id, and a fact that is absent is left out rather
than guessed. Text is presentation only: no decision reads it back.

Pinned per run (decisions.loop.card_presentation; see native_control): a
node's body is rendered once, when it is first published, and stored on the
node (``card_body``), so a later revision or a changed renderer never rewrites
a published card (native_publish compares titles and bodies exactly).
"""
from __future__ import annotations

from typing import Any

PRESENTATION_V2 = "card/v2"
LIST_MAX = 3          # names shown per group before "+n more"


def _s(v: Any) -> str:
    return "" if v is None else str(v)


def simple(name: str) -> str:
    """'a.b.C#m(x.Y,int)' -> 'C#m'; 'a.b.C' -> 'C'; 'ep:...:http' unwrapped first."""
    n = _s(name)
    if n.startswith("ep:"):
        n = n[3:]
    if n.endswith(":http"):
        n = n[: -len(":http")]
    n = n.split("(", 1)[0]
    if "#" in n:
        typ, member = n.split("#", 1)
        return "%s#%s" % (typ.rsplit(".", 1)[-1], member)
    return n.rsplit(".", 1)[-1]


def basename(path: str) -> str:
    return _s(path).replace("\\", "/").rsplit("/", 1)[-1]


def _n(count: int, word: str, plural: str = "") -> str:
    return "%d %s" % (count, word if count == 1 else (plural or word + "s"))


def _names(xs: list[str], limit: int = LIST_MAX) -> str:
    xs = list(xs)
    if len(xs) <= limit:
        return ", ".join(xs)
    return "%s, +%d more" % (", ".join(xs[:limit]), len(xs) - limit)


# ------------------------------------------------------------------ requirements

def requirement_phrase(req: dict[str, Any]) -> str:
    """A requirement in words, from its rule and structured subject."""
    rule = _s(req.get("rule")).split("/", 1)[0]
    subj = _s(req.get("subject"))
    if rule == "generator-configuration":
        coord, _, gen = subj.partition("|")
        artifact = coord.rsplit(":", 1)[-1] if coord else "the code generator"
        return "%s code generation%s" % (artifact, (" (%s)" % gen) if gen else "")
    if rule == "repository-architecture":
        impl, _, parent = subj.partition("<-")
        if parent:
            return "%s contract, implemented as %s" % (simple(parent), simple(impl))
        return "repository contract %s" % simple(impl)
    if rule == "configuration-decision":
        return "configuration decision %s" % subj
    if rule == "application-path":
        return "application path %s" % subj
    if rule == "behavior-verification":
        return "%s behavior" % simple(subj)
    if rule == "annotation-retirement":
        owner, _, ann = subj.partition("@")
        return "retire @%s on %s" % (simple(ann), simple(owner)) if ann else "retire %s" % simple(subj)
    if rule == "handler-parameter-binding":
        member, _, param = subj.partition("|")
        return "parameter %s of %s" % (param, simple(member)) if param else "parameters of %s" % simple(member)
    if rule == "request-validation":
        return "request validation of %s" % simple(subj)
    if rule == "adapter-behavior":
        return "%s adapter behavior" % subj
    return subj or _s(req.get("id"))


def short_phrase(req: dict[str, Any]) -> str:
    """The title-length form of requirement_phrase."""
    rule = _s(req.get("rule")).split("/", 1)[0]
    subj = _s(req.get("subject"))
    if rule == "generator-configuration":
        return "%s generation" % (subj.partition("|")[0].rsplit(":", 1)[-1] or "code")
    if rule == "repository-architecture":
        impl, _, parent = subj.partition("<-")
        return "%s contract" % simple(parent or impl)
    return requirement_phrase(req)


def _requirements(plan: dict[str, Any], node: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {_s(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
    return [by_id[q] for q in node.get("requirements") or [] if q in by_id]


# ------------------------------------------------------------------ checks

def check_label(check: str) -> tuple[str, str]:
    """(group, item) of one check id: the group is what a reader counts, the item what they recognize."""
    c = _s(check)
    if c.startswith("parity:sc:"):
        return "behavior scenario", c[len("parity:sc:"):]
    if c.startswith("location:"):
        return "Location header check", simple(c[len("location:"):])
    if c.startswith("behavior:repository-effects:"):
        return "repository effects check", simple(c[len("behavior:repository-effects:"):])
    if c.startswith("parity:ep:"):
        return "endpoint comparison", simple(c[len("parity:"):])
    if c.startswith("parity:"):
        return "behavior comparison", c[len("parity:"):]
    fixed = {"build:clean-generation": "clean generation", "gate:package": "packaging gate",
             "gate:startup": "startup gate", "gate:augmentation": "build augmentation gate",
             "measure:compile": "compilation", "measure:tests": "test suite", "measure:build": "build",
             "gate:compile": "compilation"}
    if c in fixed:
        return "gate", fixed[c]
    head, _, tail = c.partition(":")
    return "structural check", (tail or head).replace("-", " ")


def summarize_checks(checks: list[str]) -> str:
    """'29 behavior scenarios (create-owners, update-owners-1, +27 more), 2 Location header checks (...)'."""
    groups: dict[str, list[str]] = {}
    for c in checks:
        g, item = check_label(c)
        groups.setdefault(g, []).append(item)
    out = []
    for g, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if g == "gate":
            out.append(_names(items, 6))
            continue
        out.append("%d %s%s (%s)" % (len(items), g, "" if len(items) == 1 else "s", _names(items)))
    return "; ".join(out)


OBLIGATION_KINDS = (("err:", "compiler error"), ("inc:", "MTA finding"), ("verify:", "endpoint verification"),
                    ("plan:", "planned change"))


def obligation_counts(node: dict[str, Any]) -> list[str]:
    """['97 compiler errors', '2 MTA findings'] -- the measured or planned findings this card must remove.
    An owed scheduled check is a check (named among the checks), not a finding."""
    counts: dict[str, int] = {}
    for o in node.get("obligations") or []:
        o = _s(o)
        if o.startswith("scheduled-check:"):
            continue
        label = next((w for pre, w in OBLIGATION_KINDS if o.startswith(pre)), "other finding")
        counts[label] = counts.get(label, 0) + 1
    return [_n(c, w) for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def compact_checks(checks: list[str]) -> str:
    """A title-length name for a few checks: 'repository effects of OwnerRepository',
    'scenarios create-refused-pets, update-pets-2'."""
    groups: dict[str, list[str]] = {}
    for c in checks:
        g, item = check_label(c)
        groups.setdefault(g, []).append(item)
    out = []
    for g, items in sorted(groups.items()):
        if g == "repository effects check":
            out.append("repository effects of %s" % _names(items, 2))
        elif g == "behavior scenario":
            out.append("scenario%s %s" % ("" if len(items) == 1 else "s", _names(items, 2)))
        else:
            out.append("%s %s" % (g, _names(items, 2)))
    return "; ".join(out)


def _immediate(node: dict[str, Any]) -> list[str]:
    return [_s(c) for c in (node.get("acceptance") or {}).get("requirement_checks") or []]


def _later(node: dict[str, Any]) -> list[str]:
    acc = node.get("acceptance") or {}
    return sorted(set(_s(c) for c in acc.get("later_checks") or []) | set(_s(c) for c in node.get("deferred_checks") or []))


def _where_later(plan: dict[str, Any], node: dict[str, Any]) -> str:
    nodes = {n["outcome_id"]: n for n in plan.get("nodes") or []}
    at = list(((node.get("acceptance_states") or {}).get("later") or {}).get("at") or [])
    behavior = [simple(o[len("behavior:http:"):]) for o in at if o.startswith("behavior:http:")]
    other = [subject_of(plan, nodes[o]) if o in nodes else simple(o) for o in at if not o.startswith("behavior:http:")]
    where = []
    if behavior:
        where.append("the behavior card%s for %s" % ("" if len(behavior) == 1 else "s", _names(sorted(set(behavior)), 4)))
    where += sorted(set(other))
    if node.get("deferred_checks"):
        where.append("M4")
    return (" at " + "; ".join(where)) if where else ""


# ------------------------------------------------------------------ subjects and titles

def subject_of(plan: dict[str, Any], node: dict[str, Any]) -> str:
    """The recognizable outcome a card delivers."""
    oid = _s(node.get("outcome_id"))
    if oid.startswith("followup:"):
        sched = [_s(s.get("check")) for s in node.get("schedule") or [] if isinstance(s, dict)]
        reqs = _requirements(plan, node)
        base = requirement_phrase(reqs[0]) if reqs else _s(node.get("subject"))
        return "%s, after %s" % (compact_checks(sched), short_phrase(reqs[0]) if reqs else base) if sched else base
    if oid.startswith("requirement:"):
        reqs = _requirements(plan, node)
        if reqs:
            return requirement_phrase(reqs[0]) + ("" if len(reqs) == 1 else " (+%d related)" % (len(reqs) - 1))
    if oid.startswith("behavior:http:"):
        return "HTTP behavior of %s" % simple(oid[len("behavior:http:"):])
    subj = _s(node.get("subject") or oid)
    if subj.startswith("requirement "):
        subj = subj[len("requirement "):]
    return subj


ACTION = {"build": "BUILD", "config": "CONFIGURE", "source": "COMPILE", "runtime": "RUNTIME", "behavior": "BEHAVIOR"}


def title(plan: dict[str, Any], node: dict[str, Any]) -> str:
    """'M3 <ACTION> — <recognizable outcome>' (the existing vocabulary, a readable subject)."""
    oid = _s(node.get("outcome_id"))
    if node.get("repair_paths"):
        action = "REPAIR"
    elif oid.startswith("followup:"):
        action = "FOLLOW-UP"
    else:
        action = ACTION.get(_s(node.get("class")), "REPAIR")
    subj = subject_of(plan, node)
    if len(subj) > 110:
        subj = subj[:107].rstrip() + "..."
    return "M3 %s — %s" % (action, subj)


# ------------------------------------------------------------------ descriptions

def _goal(plan: dict[str, Any], node: dict[str, Any]) -> str:
    cls = _s(node.get("class"))
    oid = _s(node.get("outcome_id"))
    subj = subject_of(plan, node)
    if node.get("repair_paths"):
        what = _s(node.get("description")).split(" Complete when ", 1)[0].strip()
        return what if what.endswith(".") else what + "."
    if oid.startswith("followup:"):
        sched = [_s(s.get("check")) for s in node.get("schedule") or [] if isinstance(s, dict)]
        reqs = _requirements(plan, node)
        base = requirement_phrase(reqs[0]) if reqs else _s(node.get("subject"))
        return ("Repair the %s, until %s %s on the current candidate." % (base, compact_checks(sched),
                                                                        "passes" if len(sched) == 1 else "pass")
                if sched else "Repair the %s." % base)
    if oid.startswith("objective:"):
        return "%s%s, so the affected code compiles on the target platform." % (subj[:1].upper(), subj[1:])
    if cls == "behavior":
        return "Restore the source application's %s on the target platform." % subj
    if cls == "runtime":
        return "Make the application %s on the target platform." % subj
    if cls == "build":
        return "Make the destination build correct for %s." % subj
    if cls == "config":
        if subj.startswith(("configuration decision ", "application path ")):
            return "Carry the %s over to the target configuration." % subj
        return "Migrate the configuration in %s." % subj
    return "Make %s compile on the target platform." % subj


CLASS_DONE = {
    "build": "the build classpath resolves (compilation is judged on the COMPILE cards)",
    "config": "the configuration checks hold (compilation is judged on the COMPILE cards)",
    "source": "the test suite runs at M4, not here",
    "runtime": "the package and startup gate passes on the packaged candidate",
    "behavior": "the assigned scenarios are compared on the current candidate",
}


def _scope(node: dict[str, Any]) -> str:
    paths = [_s(p) for p in node.get("plan_paths") or []]
    parts = []
    if paths:
        parts.append("%d file%s (%s)" % (len(paths), "" if len(paths) == 1 else "s", _names([basename(p) for p in paths])))
    eps = [_s(e) for e in node.get("entry_points") or []]
    if eps:
        parts.append("%d endpoint%s (%s)" % (len(eps), "" if len(eps) == 1 else "s", _names([simple(e) for e in eps])))
    return "; ".join(parts)


def description(plan: dict[str, Any], node: dict[str, Any]) -> str:
    """The card body of a repair outcome (card/v2)."""
    found = obligation_counts(node)
    now, later = _immediate(node), _later(node)
    done = []
    if found:
        done.append("its %s %s gone from the measured work list" % (" and ".join(found),
                                                                     "is" if found == ["1" + f[1:] for f in found] and len(found) == 1 and found[0].startswith("1 ") else "are"))
    if now:
        done.append("%s %s on the current candidate: %s" % (_n(len(now), "check"), "passes" if len(now) == 1 else "pass",
                                                            summarize_checks(now)))
    if not found and not now:
        done.append("no finding or requirement check is assigned to it here")
    cls_done = CLASS_DONE.get(_s(node.get("class")))
    if cls_done:
        done.append(cls_done)
    parts = [_goal(plan, node)]
    scope = _scope(node)
    if scope:
        parts.append("Scope: %s." % scope)
    parts.append("Done when: %s; and the reviewer approves." % "; ".join(done))
    if later:
        parts.append("Checked later, not by this card: %s (%s)%s. Approving this card does not discharge %s."
                     % (_n(len(later), "check"), summarize_checks(later), _where_later(plan, node),
                        "it" if len(later) == 1 else "them"))
    lin = next((x for x in node.get("lineage") or [] if isinstance(x, dict)), None)
    if lin:
        nodes = {n["outcome_id"]: n for n in plan.get("nodes") or []}
        finder = nodes.get(_s(lin.get("found_by")))
        follows = nodes.get(_s(lin.get("follows")))
        parts.append("Why this card exists: the \"%s\" card measured these checks failing after the \"%s\" card had "
                     "been accepted. That card stays accepted; this card owns the repair."
                     % (subject_of(plan, finder) if finder else simple(_s(lin.get("found_by"))),
                        subject_of(plan, follows) if follows else simple(_s(lin.get("follows")))))
    parts.append("Details: the attached contract.json lists every requirement, check and finding.\n"
                 "Procedure: paved-road-m3 (outcome-board/v2). A rejected attempt or a review change request comes back "
                 "to this same card.")
    return "\n\n".join(parts)


def assess_description(plan: dict[str, Any], node: dict[str, Any]) -> str:
    deferred = (node.get("acceptance") or {}).get("deferred_requirement_checks") or []
    owners = sorted({_s(d.get("outcome")) for d in deferred if isinstance(d, dict)})
    extra = ("\n\nAlso measured here: %d check%s earlier cards could not measure (%s), owed by %d card%s."
             % (len(deferred), "" if len(deferred) == 1 else "s",
                summarize_checks([_s(d.get("check")) for d in deferred if isinstance(d, dict)]),
                len(owners), "" if len(owners) == 1 else "s")) if deferred else ""
    return ("Verify the combined migrated application on its packaged candidate.%s\n\n"
            "Done when: the M4 verdict is ACCEPT or PROVISIONAL_ACCEPT for the current candidate and the reviewer "
            "approves. A REFUSE keeps this card open: the repairs it needs become its prerequisites, and it runs "
            "again after them. Delivery (M5) starts only after this card is done.\n\n"
            "Details: the attached contract.json lists the prerequisite outcomes and the checks.\n"
            "Procedure: paved-road-m4 (outcome-board/v2)." % extra)


# ------------------------------------------------------------------ handoff

def handoff_summary(title_: str, node: dict[str, Any], last: dict[str, Any], *, accepted_now: bool,
                    rejects: int, budget: dict[str, Any]) -> str:
    """The review handoff of a repair card: decision, execution per stage, each immediate check's result,
    what stays for later. A check is reported passing only when the measurement says pass."""
    m = last.get("measurement") or {}
    commit = _s(last.get("commit"))[:12] or "none"
    head = ("%s: implementation ready for review on commit %s (accepted on the current tree)." % (title_, commit)
            if accepted_now else "%s: NOT accepted on the current tree (last candidate %s)." % (title_, commit))
    ex = m.get("execution") or {}
    stages = ["%s %s" % (k, _s((v or {}).get("state")) or "unknown") for k, v in sorted(ex.items())] if ex else \
        ["%s asserted by worker receipt" % c for c in m.get("classes") or []]
    unmet = m.get("unmet_checks") or {}
    kept = _immediate(node)
    passed = set(m.get("checks") or [])
    states = {"pass": [], "fail": [], "unknown": [], "other": []}
    for c in kept:
        st = "pass" if c in passed else _s(next((v.get("status") for k, v in unmet.items() if k == c or k.endswith("|" + c)), ""))
        states[st if st in states else ("unknown" if not st else "other")].append(c)
    parts = [head]
    if stages:
        parts.append("Execution: %s." % ", ".join(stages))
    if kept:
        tally = ", ".join("%d %s" % (len(v), k if k != "other" else "blocked") for k, v in states.items() if v)
        bad = states["fail"] + states["unknown"] + states["other"]
        parts.append("Checks judged here (%d): %s%s." % (len(kept), tally,
                                                         ("; not passing: %s" % summarize_checks(bad)) if bad else ""))
    later = _later(node)
    if later:
        parts.append("Checked later, not discharged by this review: %d (%s)." % (len(later), summarize_checks(later)))
    open_owned = m.get("open_owned") or []
    parts.append("Open findings owned here: %d. Rejected attempts on this card: %d; budget %s of %s."
                 % (len(open_owned), rejects, budget.get("spent"), budget.get("limit")))
    return " ".join(parts)
