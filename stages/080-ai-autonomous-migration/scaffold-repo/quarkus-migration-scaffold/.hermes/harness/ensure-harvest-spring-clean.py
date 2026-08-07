#!/usr/bin/env python3
"""O-HARVESTSPRING plugin: strip Spring residue after harvest preseed.

Invoked by ``ensure-harvest-ready.py`` when on-disk Java still cites
``org.springframework``. Migration-general mechanical transforms aligned with
O-FIDELITYDAO / O-FIDELITYSORT / O-SPRINGRESIDUE / O-BINDERRDROP / O-ORFFSHIM:

- drop ``@DateTimeFormat`` + import (LocalDate fields stay)
- ``PropertyComparator.sort(list, new MutableSortDefinition("prop",…))``
  → ``list.sort(Comparator.comparing(…))`` keeping ArrayList locals
- drop ``ToStringCreator`` builder blocks → simple ``toString()``
- ``BindingResult``/``FieldError`` → Jakarta ``ConstraintViolation`` (O-BINDERRDROP)
- ``ObjectRetrievalFailureException`` → ``EntityNotFoundException`` (O-ORFFSHIM)
- remove leftover ``org.springframework.*`` imports

Without this, O-HARVESTSTALL preseed leaves SPRINGRESIDUE RED → Qwen 0-write
→ MiniMax (Wave5 S01-T-006), or compile-RED delete/shim escapes (S02 T-003/T-007).
Compile-deps alone (O-HARVESTREADY valdep/dskind) are not acceptance-ready.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SRC = ROOT / "src" / "main" / "java"

_SPRING_IMPORT = re.compile(
    r"^import\s+org\.springframework\.[^;]+;\s*\n", re.M
)
_DATETIME_ANN = re.compile(
    r"^[ \t]*@DateTimeFormat\b[^\n]*\n", re.M
)
_PROP_SORT = re.compile(
    r"PropertyComparator\.sort\(\s*(\w+)\s*,\s*"
    r"new\s+MutableSortDefinition\(\s*\"([A-Za-z0-9_]+)\"\s*,\s*"
    r"(true|false)\s*,\s*(true|false)\s*\)\s*\)\s*;"
)
_TOSTRING_CREATOR = re.compile(
    r"return\s+new\s+ToStringCreator\s*\(\s*this\s*\)\s*"
    r"(?:\.\s*append\s*\(\s*\"([^\"]+)\"\s*,\s*([^)]+)\)\s*)+"
    r"\.\s*toString\s*\(\s*\)\s*;",
    re.S,
)


def _prop_getter(prop: str) -> str:
    if not prop:
        return "toString"
    return "get" + prop[0].upper() + prop[1:]


_ORFF_NEW = re.compile(
    r"new\s+ObjectRetrievalFailureException\s*\(\s*([^,]+)\s*,\s*([^)]+)\)"
)


def _ensure_import(text: str, import_line: str) -> tuple[str, bool]:
    """Insert import after package if missing. Returns (text, inserted)."""
    stmt = import_line if import_line.endswith(";") else import_line + ";"
    simple = stmt.rstrip(";").split(".")[-1]
    if re.search(rf"import\s+[\w.]*\b{re.escape(simple)}\s*;", text):
        return text, False
    if re.search(r"import\s+jakarta\.validation\.\*\s*;", text) and "ConstraintViolation" in stmt:
        return text, False
    if re.search(r"import\s+jakarta\.persistence\.\*\s*;", text) and "EntityNotFoundException" in stmt:
        return text, False
    if re.search(r"import\s+java\.util\.\*\s*;", text) and stmt.endswith("java.util.List;"):
        return text, False
    new, n = re.subn(
        r"(package\s+[^;]+;\s*\n)",
        r"\1" + stmt + "\n",
        text,
        count=1,
    )
    return (new, True) if n else (text, False)


def transform(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    springish = (
        "org.springframework" in text
        or "PropertyComparator" in text
        or "BindingResult" in text
        or "FieldError" in text
        or "ObjectRetrievalFailureException" in text
    )
    if not springish:
        return text, notes

    out = text

    # O-BINDERRDROP: Spring validation types → Jakarta ConstraintViolation
    # before import strip (else compile RED → worker deletes addAllErrors).
    if "BindingResult" in out or "FieldError" in out:
        out2 = out
        # for (FieldError fe : br.getFieldErrors()) → for (… fe : br)
        out2 = re.sub(
            r"\b(\w+)\.getFieldErrors\s*\(\s*\)",
            r"\1",
            out2,
        )
        # fieldError.getObjectName() → …getRootBeanClass().getSimpleName()
        # (only FieldError receivers — do not touch error.setObjectName)
        out2 = re.sub(
            r"\b((?i:fieldError|FieldError)\w*)\.getObjectName\s*\(\s*\)",
            r"\1.getRootBeanClass().getSimpleName()",
            out2,
        )
        out2 = re.sub(r"\bBindingResult\b", "List<ConstraintViolation<?>>", out2)
        out2 = re.sub(r"\bFieldError\b", "ConstraintViolation<?>", out2)
        if out2 != out:
            out = out2
            notes.append("bindingresult-constraintviolation")
            out, ins = _ensure_import(out, "import jakarta.validation.ConstraintViolation;")
            if ins:
                notes.append("constraintviolation-import")
            out, ins = _ensure_import(out, "import java.util.List;")
            if ins:
                notes.append("list-import")

    # O-ORFFSHIM: Spring ORM exception → JPA EntityNotFoundException
    # (MAPPINGS / EXECUTION approved). Never leave the Spring type for a
    # worker to shim as com.demo.util.ObjectRetrievalFailureException.
    # Rename types only outside import lines — otherwise
    # `import org.springframework.orm.ObjectRetrievalFailureException`
    # becomes a fake EntityNotFound import that spring-strip then deletes.
    orff_needed = "ObjectRetrievalFailureException" in out
    if orff_needed:
        out2, n = _ORFF_NEW.subn(
            r'new EntityNotFoundException(String.valueOf(\1) + " id=" + \2)',
            out,
        )
        if n:
            out = out2
            notes.append(f"orff-new={n}")
        lines = []
        type_hits = 0
        for ln in out.splitlines(True):
            if "import " in ln and "org.springframework" in ln:
                lines.append(ln)
                continue
            ln2, n = re.subn(
                r"\bObjectRetrievalFailureException\b",
                "EntityNotFoundException",
                ln,
            )
            type_hits += n
            lines.append(ln2)
        if type_hits:
            out = "".join(lines)
            notes.append(f"orff-type={type_hits}")

    if _SPRING_IMPORT.search(out):
        out = _SPRING_IMPORT.sub("", out)
        notes.append("spring-imports-dropped")
    if _DATETIME_ANN.search(out):
        out = _DATETIME_ANN.sub("", out)
        notes.append("datetimeformat-dropped")

    if orff_needed and "EntityNotFoundException" in out:
        out, ins = _ensure_import(
            out, "import jakarta.persistence.EntityNotFoundException;"
        )
        if ins:
            notes.append("entitynotfound-import")

    def repl_sort(m: re.Match[str]) -> str:
        var, prop, ignore_case, _asc = m.group(1), m.group(2), m.group(3), m.group(4)
        getter = _prop_getter(prop)
        # Always lambda — method-refs need element type (sortedSpecialties≠Spec).
        if ignore_case == "true" and prop.lower() in {"name", "lastname", "firstname"}:
            return (
                f"{var}.sort(Comparator.comparing("
                f"x -> x.{getter}(), String.CASE_INSENSITIVE_ORDER));"
            )
        return f"{var}.sort(Comparator.comparing(x -> x.{getter}()));"

    new_out, n = _PROP_SORT.subn(repl_sort, out)
    if n:
        out = new_out
        notes.append(f"propertycomparator-jdk={n}")

    # ToStringCreator → plain concatenation of append pairs.
    def repl_ts(m: re.Match[str]) -> str:
        body = m.group(0)
        pairs = re.findall(
            r"\.\s*append\s*\(\s*\"([^\"]+)\"\s*,\s*([^)]+)\)", body
        )
        if not pairs:
            return 'return getClass().getSimpleName();'
        parts = ['"' + k + '=" + ' + v.strip() for k, v in pairs]
        return "return " + ' + ", " + '.join(parts) + ";"

    new_out, n = _TOSTRING_CREATOR.subn(repl_ts, out)
    if n:
        out = new_out
        notes.append(f"tostringcreator-plain={n}")

    # Ensure Comparator import when we introduced Comparator.comparing
    if "Comparator.comparing" in out and not re.search(
        r"import\s+java\.util\.Comparator\s*;", out
    ):
        if re.search(r"import\s+java\.util\.\*\s*;", out):
            pass
        else:
            out = re.sub(
                r"(package\s+[^;]+;\s*\n)",
                r"\1\nimport java.util.Comparator;\n",
                out,
                count=1,
            )
            notes.append("comparator-import")

    # Drop any remaining spring import lines (wildcard / odd forms)
    if "org.springframework" in out:
        out2 = "\n".join(
            ln
            for ln in out.splitlines(True)
            if "org.springframework" not in ln
        )
        if out2 != out:
            out = out2
            notes.append("spring-lines-stripped")

    return out, notes


def main() -> int:
    if not SRC.is_dir():
        print("skip:no-src")
        return 0
    touched = 0
    all_notes: list[str] = []
    for path in SRC.rglob("*.java"):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            "org.springframework" not in raw
            and "PropertyComparator" not in raw
            and "BindingResult" not in raw
            and "FieldError" not in raw
            and "ObjectRetrievalFailureException" not in raw
        ):
            continue
        new, notes = transform(raw)
        if new != raw:
            path.write_text(new, encoding="utf-8")
            touched += 1
            all_notes.extend(notes)
    if not touched:
        print("skip:no-spring-residue")
        return 0
    print("ok:files=" + str(touched) + "," + ",".join(all_notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
