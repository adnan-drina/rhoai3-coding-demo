#!/usr/bin/env python3
"""decisions selftest: the security section (ADR-014).

Who the enabled-mode source capture authenticates as is the Operator's
DECISION, recorded in the one human-authored file and backed by an ADR -- not
an argument typed at a shell that binds to nothing and survives no run. This
file is read, digested and copied into evidence, so what it may hold is
narrow: the source's security switch by KEY, and each seeded identity by the
NAME of the environment variable holding its credential. A credential written
where its name belongs is refused by NAME of the field, never echoed.

The section is OPTIONAL: a specimen with no security switch has no enabled
mode, and the M1 road steps record that as their reason. What is refused is a
section that is there and half-declared, because the capture would otherwise
start the source with a switch nobody named.

Also the tree this suite is running in is checked, but only for what is
actually true of it: a security section, if the tree's own decisions.yaml
declares one, must load, validate and yield a decision with no gaps -- but a
destination BEFORE the Operator records ADR-014 declares none, and that is
not a failure of this suite, only of a claim it never makes. The scaffold's
own declared shape (one switch, one identity with three roles, two
credential references by name) is instead proven from a fixture, below, so
that proof does not depend on which tree happens to host this file.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
GOLDEN = HERE.parents[2]

from planner import specimens  # noqa: E402
from planner.decisions import (DecisionsError, load_decisions, missing_decisions,  # noqa: E402
                               security, security_gaps)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _section(**over: Any) -> dict[str, Any]:
    """A well-formed section under names no specimen owns."""
    sec: dict[str, Any] = {
        "adr": "ADR-003",
        "switch": {"key": "acme.security.enable", "disabled_value": "off", "enabled_value": "on"},
        "identities": [{"name": "an-identity", "credential_ref": "ACME_IDENTITY_CREDENTIAL",
                        "roles": ["ROLE_ONE", "ROLE_TWO"]}],
        "invalid_credential_ref": "ACME_INVALID_CREDENTIAL",
    }
    sec.update(over)
    return sec


def _doc(sec: Any = None) -> dict[str, Any]:
    doc = specimens.full_decisions()
    if sec is not None:
        doc["security"] = sec
    return doc


def _classes(gaps: list[dict[str, str]]) -> list[tuple[str, str]]:
    return sorted((g["class"], g["subject"]) for g in gaps)


def _absent_case() -> int:
    """No section is not a gap, and not a half-answer either."""
    doc = _doc()
    if security_gaps(doc) or security(doc) != {}:
        return _fail("an absent security section is no gap and no decision: %s %s" % (security_gaps(doc), security(doc)))
    if any(g["subject"].startswith("security") for g in missing_decisions(doc, GOLDEN)):
        return _fail("an absent section must not block admission")
    return 0


def _well_formed_case() -> int:
    doc = _doc(_section())
    if security_gaps(doc):
        return _fail("a well-formed section holds: %s" % security_gaps(doc))
    got = security(doc)
    if got != {"adr": "ADR-003",
               "switch": {"key": "acme.security.enable", "disabled_value": "off", "enabled_value": "on"},
               "identities": [{"name": "an-identity", "credential_ref": "ACME_IDENTITY_CREDENTIAL",
                               "roles": ["ROLE_ONE", "ROLE_TWO"]}],
               "invalid_credential_ref": "ACME_INVALID_CREDENTIAL",
               "request_policy": "", "fixtures": []}:
        return _fail("the decided section is read as it was written: %s" % got)
    # the ADR is the backing, not decoration
    doc = _doc(_section(adr="ADR-404"))
    if _classes(security_gaps(doc)) != [("ADR_NOT_ACCEPTED", "security")] or security(doc):
        return _fail("a section citing an ADR nobody accepted is not a decision: %s" % security_gaps(doc))
    return 0


def _credential_shape_case() -> int:
    """A reference is a NAME. ``user:password`` and anything with whitespace
    are the credential itself, and are refused by the field that carries
    them -- the refusal never repeats the value."""
    for bad in ("an-identity:its-password", "ACME CREDENTIAL", " ACME_CREDENTIAL"):
        doc = _doc(_section(identities=[{"name": "an-identity", "credential_ref": bad}]))
        gaps = security_gaps(doc)
        if _classes(gaps) != [("SECURITY_LITERAL_CREDENTIAL", "security.identities[0].credential_ref")]:
            return _fail("a credential where a NAME belongs is refused: %r → %s" % (bad, gaps))
        if any(bad.strip() in g["detail"] for g in gaps):
            return _fail("the refusal names the field, never what it holds: %s" % gaps)
        if security(doc):
            return _fail("a refused section is not a decision")
    doc = _doc(_section(invalid_credential_ref="an-identity:its-password"))
    if _classes(security_gaps(doc)) != [("SECURITY_LITERAL_CREDENTIAL", "security.invalid_credential_ref")]:
        return _fail("the invalid credential is a reference too: %s" % security_gaps(doc))
    # an identity that names no reference cannot be authenticated as
    doc = _doc(_section(identities=[{"name": "an-identity", "roles": ["ROLE_ONE"]}]))
    if _classes(security_gaps(doc)) != [("MISSING_DECISION", "security.identities[0].credential_ref")]:
        return _fail("an identity without a credential_ref is a gap: %s" % security_gaps(doc))
    return 0


def _switch_case() -> int:
    for field in ("key", "disabled_value", "enabled_value"):
        sw = dict(_section()["switch"])
        sw.pop(field)
        doc = _doc(_section(switch=sw))
        if ("MISSING_DECISION", "security.switch.%s" % field) not in _classes(security_gaps(doc)):
            return _fail("a half-declared switch is a gap: %s missing → %s" % (field, security_gaps(doc)))
    doc = _doc(_section(switch={"key": "acme.security.enable", "disabled_value": "same", "enabled_value": "same"}))
    if ("MISSING_DECISION", "security.switch.enabled_value") not in _classes(security_gaps(doc)):
        return _fail("two behaviours need two values: %s" % security_gaps(doc))
    doc = _doc(_section(identities=[{"name": "who", "credential_ref": "A"}, {"name": "who", "credential_ref": "B"}]))
    if ("MISSING_DECISION", "security.identities[1].name") not in _classes(security_gaps(doc)):
        return _fail("one identity declared twice is a gap: %s" % security_gaps(doc))
    doc = _doc("not a mapping")
    if _classes(security_gaps(doc)) != [("MISSING_DECISION", "security")]:
        return _fail("a section that is not a mapping is a gap: %s" % security_gaps(doc))
    return 0


def _file_case() -> int:
    """The schema accepts the section on disk, and the scaffold's own file
    declares the one ADR-014 asks for."""
    with tempfile.TemporaryDirectory(prefix="decisions-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"),
                                    decisions=_doc(None))
        text = (root / "decisions.yaml").read_text(encoding="utf-8")
        (root / "decisions.yaml").write_text(
            text
            + 'security:\n  adr: "ADR-003"\n'
              '  switch:\n    key: "acme.security.enable"\n    disabled_value: "off"\n    enabled_value: "on"\n'
              '  identities:\n    - name: "an-identity"\n      credential_ref: "ACME_IDENTITY_CREDENTIAL"\n'
              '      roles:\n        - "ROLE_ONE"\n'
              '  invalid_credential_ref: "ACME_INVALID_CREDENTIAL"\n', encoding="utf-8")
        try:
            doc = load_decisions(root)
        except DecisionsError as exc:
            return _fail("the schema accepts a declared security section: %s" % exc)
        if security(doc)["switch"]["key"] != "acme.security.enable":
            return _fail("the section survives the round trip: %s" % security(doc))
        # a key the schema does not know is refused at the file, not ignored
        (root / "decisions.yaml").write_text(text + 'security:\n  password: "a-password"\n', encoding="utf-8")
        try:
            load_decisions(root)
        except DecisionsError:
            pass
        else:
            return _fail("a security section carrying an unknown key must be refused by the schema")

    # This suite is installed onto a destination too, where decisions.yaml is
    # the destination's own live file and legitimately declares no security
    # section until the Operator records ADR-014. Assert only what is true
    # of THIS tree's file: if it declares a section, it must hold with no
    # gaps; if it declares none, that is not a gap either.
    doc = load_decisions(GOLDEN)
    if missing_decisions(doc, GOLDEN):
        return _fail("the tree's own decisions.yaml holds: %s" % missing_decisions(doc, GOLDEN))
    if doc.get("security") is None:
        print("tree declares no security section (a destination before the Operator records ADR-014; "
              "the fixture cases above cover the schema)")
        return 0
    gaps = security_gaps(doc)
    if gaps:
        return _fail("the tree's own security section holds: %s" % gaps)
    decided = security(doc)
    if not decided["switch"]["key"] or decided["switch"]["disabled_value"] == decided["switch"]["enabled_value"]:
        return _fail("the tree's switch is named with two settings: %s" % decided["switch"])
    for row in decided["identities"] + [{"credential_ref": decided["invalid_credential_ref"]}]:
        ref = str(row.get("credential_ref") or "")
        if ref and (":" in ref or any(c.isspace() for c in ref)):
            return _fail("every credential in the tree's file is a REFERENCE: %r" % ref)
    print("checked the tree's own security section")
    return 0


# The exact security: block the scaffold's own decisions.yaml carries for
# ADR-014 (copied verbatim) -- proves the scaffold's declared shape from a
# fixture, independent of whichever tree `_file_case` above happens to run
# against.
_SCAFFOLD_SECURITY_YAML = (
    'security:\n'
    '  adr: ADR-014\n'
    '  switch:\n'
    '    key: petclinic.security.enable\n'
    '    disabled_value: "false"\n'
    '    enabled_value: "true"\n'
    '  identities:\n'
    '    - name: admin\n'
    '      credential_ref: PETCLINIC_ADMIN_CREDENTIAL\n'
    '      roles:\n'
    '        - ROLE_OWNER_ADMIN\n'
    '        - ROLE_VET_ADMIN\n'
    '        - ROLE_ADMIN\n'
    '  invalid_credential_ref: PETCLINIC_INVALID_CREDENTIAL\n'
    '  request_policy: authenticated\n'
    '  fixtures:\n'
    '    - name: identity-disabled\n'
    '      intent: refuse\n'
    '      scenarios: auth-allowed\n'
    '      dataset_config_key: spring.sql.init.data-locations\n'
    '      statements:\n'
    "        - UPDATE users SET enabled = false WHERE username = 'admin'\n"
)


def _scaffold_shape_case() -> int:
    """The scaffold's own security section -- one switch, one identity with
    three roles, two credential references by name -- parses clean from a
    fixture built with exactly that shape, so the proof holds regardless of
    what any installed tree's live decisions.yaml happens to declare."""
    base = specimens.full_decisions(adrs=list(specimens.ACCEPTED_ADRS)
                                     + [{"id": "ADR-014", "title": "Preserve source security switch", "status": "accepted"}])
    with tempfile.TemporaryDirectory(prefix="decisions-shape-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=base)
        text = (root / "decisions.yaml").read_text(encoding="utf-8")
        (root / "decisions.yaml").write_text(text + _SCAFFOLD_SECURITY_YAML, encoding="utf-8")
        doc = load_decisions(root)
    if security_gaps(doc):
        return _fail("the scaffold's declared shape holds with no gaps: %s" % security_gaps(doc))
    decided = security(doc)
    if decided["switch"] != {"key": "petclinic.security.enable", "disabled_value": "false", "enabled_value": "true"}:
        return _fail("the scaffold's switch is named with two distinct settings: %s" % decided["switch"])
    if len(decided["identities"]) != 1 or decided["identities"][0]["roles"] != ["ROLE_OWNER_ADMIN", "ROLE_VET_ADMIN", "ROLE_ADMIN"]:
        return _fail("the scaffold's shape is one identity with three roles: %s" % decided["identities"])
    if (decided["identities"][0]["credential_ref"] != "PETCLINIC_ADMIN_CREDENTIAL"
            or decided["invalid_credential_ref"] != "PETCLINIC_INVALID_CREDENTIAL"):
        return _fail("both credentials are referenced by NAME: %s / %s"
                      % (decided["identities"][0]["credential_ref"], decided["invalid_credential_ref"]))
    # ... and what ADR-014's exits added: the request policy the source's
    # enabled configuration applies to every request, and the one variant of
    # the baseline the seed cannot reach
    if decided["request_policy"] != "authenticated":
        return _fail("the scaffold declares what its enabled configuration requires of every request: %s" % decided["request_policy"])
    if len(decided["fixtures"]) != 1 or decided["fixtures"][0]["name"] != "identity-disabled":
        return _fail("the scaffold declares one variant of the source baseline: %s" % decided["fixtures"])
    fx = decided["fixtures"][0]
    if (fx["intent"] != "refuse" or fx["scenarios"] != "auth-allowed"
            or fx["dataset_config_key"] != "spring.sql.init.data-locations" or len(fx["statements"]) != 1):
        return _fail("the variant states its intent, the class it varies, the dataset key and its statements: %s" % fx)
    # the statements travel verbatim: they are what the variant IS, and a run
    # nobody can re-apply them from is not reproducible
    if fx["statements"] != ["UPDATE users SET enabled = false WHERE username = 'admin'"]:
        return _fail("the declared statements are read back exactly as written: %s" % fx["statements"])
    return 0


def _request_policy_case() -> int:
    """What the source's ENABLED configuration requires of a request no
    annotation names.

    A source configured with ``anyRequest().authenticated()`` guards the
    routes that carry no ``@PreAuthorize`` as surely as the annotated ones,
    and only the Operator can read that off the source's own configuration --
    so it is declared here, and a value nothing implements is refused rather
    than recorded, because the producers would silently probe nothing for it.
    Absent is not a gap: a specimen whose configuration requires nothing of an
    unannotated route has none."""
    doc = _doc(_section(request_policy="authenticated"))
    if security_gaps(doc) or security(doc)["request_policy"] != "authenticated":
        return _fail("a declared request policy holds and is read back: %s %s" % (security_gaps(doc), security(doc)))
    if security(_doc(_section()))["request_policy"] != "":
        return _fail("an absent request policy is empty, not invented")
    doc = _doc(_section(request_policy="whatever-the-source-does"))
    if _classes(security_gaps(doc)) != [("MISSING_DECISION", "security.request_policy")] or security(doc):
        return _fail("a request policy nothing implements is refused, not recorded: %s" % security_gaps(doc))
    return 0


def _fixtures_case() -> int:
    """A separately recorded variant of the source baseline.

    Its name becomes a directory, its statements are the SPECIMEN's own SQL
    (this loader parses none of it -- only that there is at least one, and
    that each is a non-empty string), the scenario class names a class the
    producers derive, and dataset_config_key is the configuration property the
    source reads its dataset location from. An intent nobody declared means
    the variant expects whatever the source answers, which is the honest
    default; an intent nothing implements is refused."""
    fixture = {"name": "identity-disabled", "intent": "refuse", "scenarios": "auth-allowed",
               "dataset_config_key": "acme.sql.init.data-locations",
               "statements": ["UPDATE accounts SET enabled = false WHERE name = 'an-identity'"]}
    doc = _doc(_section(fixtures=[fixture]))
    if security_gaps(doc):
        return _fail("a well-formed fixture holds: %s" % security_gaps(doc))
    got = security(doc)["fixtures"]
    if got != [fixture]:
        return _fail("the fixture is read back as it was declared, statements and all: %s" % got)
    if security(_doc(_section()))["fixtures"] != []:
        return _fail("no fixture is not an empty one nobody declared")
    # every field is checked as what it IS
    for over, subject in (
            ({"name": "Identity Disabled"}, "security.fixtures[0].name"),
            ({"name": ""}, "security.fixtures[0].name"),
            ({"statements": []}, "security.fixtures[0].statements"),
            ({"statements": ["  "]}, "security.fixtures[0].statements"),
            ({"scenarios": "whatever"}, "security.fixtures[0].scenarios"),
            ({"scenarios": ""}, "security.fixtures[0].scenarios"),
            ({"dataset_config_key": ""}, "security.fixtures[0].dataset_config_key"),
            ({"dataset_config_key": "a key with spaces"}, "security.fixtures[0].dataset_config_key"),
            ({"intent": "accept"}, "security.fixtures[0].intent")):
        doc = _doc(_section(fixtures=[dict(fixture, **over)]))
        if ("MISSING_DECISION", subject) not in _classes(security_gaps(doc)):
            return _fail("%s must be checked as what it is: %s → %s" % (subject, over, security_gaps(doc)))
        if security(doc):
            return _fail("a refused fixture is not a decision: %s" % over)
    doc = _doc(_section(fixtures=[fixture, dict(fixture, statements=["DELETE FROM accounts"])]))
    if ("MISSING_DECISION", "security.fixtures[1].name") not in _classes(security_gaps(doc)):
        return _fail("one variant declared twice is a gap: %s" % security_gaps(doc))
    # an intent nobody declared is the honest default, not a gap
    del fixture["intent"]
    doc = _doc(_section(fixtures=[fixture]))
    if security_gaps(doc) or security(doc)["fixtures"][0]["intent"] != "":
        return _fail("a fixture with no declared intent holds and expects nothing: %s" % security_gaps(doc))
    return 0


def main() -> int:
    if (_absent_case() or _well_formed_case() or _credential_shape_case() or _switch_case() or _file_case()
            or _request_policy_case() or _fixtures_case() or _scaffold_shape_case()):
        return 1
    print("OK: decisions (the security section is optional and, when present, must name an accepted ADR, the source's switch with two "
          "distinct settings, and each seeded identity once by the NAME of the variable holding its credential; a credential written "
          "where a name belongs -- user:password, or anything carrying whitespace -- is refused by field and never echoed, an identity "
          "with no credential_ref and a half-declared switch are gaps, a refused section is not a decision, the schema refuses a key "
          "nobody declared, the tree hosting this suite is checked only for what it actually declares, and a fixture carrying the "
          "scaffold's own shape parses clean with one identity, three roles, both credentials referenced by name, the request "
          "policy its enabled configuration applies to every request, and one declared variant of the source baseline whose "
          "name, statements, scenario class, dataset key and intent are each checked as what they are)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
