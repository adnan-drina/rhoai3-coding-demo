#!/usr/bin/env python3
"""Specimen-agnostic generated-source classification (no Dto/name patterns).

A type is generated when any of:
  - its path sits under target/generated-sources/
  - the type file carries an @Generated annotation
  - a generator plugin is declared in a build file AND the type is not in
    src/ AND (package matches plugin config OR unique basename under
    target/generated-sources/)

Used by stamp (provider: generated), assert-dependency-closure (skip
DEST_MISS; require generator inputs owned), and type-inventory.
"""
from __future__ import annotations

import re
from pathlib import Path

GENERATED_DIR = "target/generated-sources"
GENERATED_ANN_RE = re.compile(
    r"@\s*(?:(?:javax|jakarta)\.annotation\.|com\.google\.|org\.openapitools\.)?"
    r"Generated\b"
)
PLUGIN_BLOCK_RE = re.compile(r"<plugin>(.*?)</plugin>", re.S | re.I)
ARTIFACT_RE = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>", re.I)
INPUT_SPEC_RE = re.compile(
    r"<(?:inputSpec|openAPISpec|openapiFile|schemaFile|specFile|"
    r"protoSourceRoot|wsdlFile|wsdlFiles)\s*>\s*([^<]+?)\s*</",
    re.I,
)
PACKAGE_RE = re.compile(
    r"<(?:modelPackage|apiPackage|invokerPackage|packageName|"
    r"sourcePackage)\s*>\s*([^<]+?)\s*</",
    re.I,
)
OUTPUT_DIR_RE = re.compile(
    r"<(?:outputDirectory|outputDir|output)\s*>\s*([^<]+?)\s*</",
    re.I,
)
GENERATOR_AID_RE = re.compile(
    r"(?i)(openapi-generator|swagger-codegen|protobuf|protoc|"
    r"jaxb2?-maven|jaxb-maven|wsdl2java|jsonschema2pojo|"
    r"avro-maven|mapstruct|lombok|kotlin-maven-plugin|openapi)"
)
NOT_GENERATOR_AIDS = frozenset(
    {
        "maven-compiler-plugin",
        "maven-surefire-plugin",
        "maven-failsafe-plugin",
        "maven-resources-plugin",
        "maven-jar-plugin",
        "maven-war-plugin",
        "maven-source-plugin",
        "maven-javadoc-plugin",
        "maven-deploy-plugin",
        "maven-install-plugin",
        "quarkus-maven-plugin",
    }
)
BUILD_NAMES = ("pom.xml", "build.gradle", "build.gradle.kts")


def _rel_posix(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def path_is_generated(path: str | Path) -> bool:
    p = _rel_posix(str(path))
    return f"/{GENERATED_DIR}/" in f"/{p}/" or p.startswith(GENERATED_DIR + "/")


def file_has_generated_annotation(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(GENERATED_ANN_RE.search(text))


def _strip_maven_prop(value: str) -> str:
    v = value.strip().strip('"').strip("'")
    v = re.sub(r"\$\{[^}]+\}/?", "", v)
    return _rel_posix(v)


def parse_generator_plugins(build_text: str) -> list[dict]:
    """Extract generator plugin blocks from Maven/Gradle text."""
    found: list[dict] = []
    for block in PLUGIN_BLOCK_RE.findall(build_text or ""):
        am = ARTIFACT_RE.search(block)
        aid = (am.group(1).strip() if am else "").strip()
        if aid in NOT_GENERATOR_AIDS:
            continue
        specs = [_strip_maven_prop(x) for x in INPUT_SPEC_RE.findall(block)]
        packages = [x.strip() for x in PACKAGE_RE.findall(block) if x.strip()]
        outputs = [_strip_maven_prop(x) for x in OUTPUT_DIR_RE.findall(block)]
        gen_out = [o for o in outputs if GENERATED_DIR in o.replace("\\", "/")]
        is_gen = bool(
            specs
            or gen_out
            or (aid and GENERATOR_AID_RE.search(aid))
        )
        if not is_gen:
            continue
        found.append(
            {
                "artifactId": aid,
                "input_specs": [s for s in specs if s],
                "packages": packages,
                "output_dirs": gen_out or outputs,
            }
        )
    # Gradle: inputSpec / proto files without <plugin> XML
    if not found and build_text:
        for m in re.finditer(
            r"(?i)inputSpec(?:\s*=\s*|\.set\(\s*)['\"]([^'\"]+)['\"]",
            build_text,
        ):
            found.append(
                {
                    "artifactId": "gradle-generator",
                    "input_specs": [_strip_maven_prop(m.group(1))],
                    "packages": [],
                    "output_dirs": [],
                }
            )
    return found


def _read_build(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def iter_dest_build_files(root: Path) -> list[Path]:
    """Dest pom/gradle only. Mint-time GENERATOR_INPUTS must not inherit legacy."""
    out: list[Path] = []
    for name in BUILD_NAMES:
        p = root / name
        if p.is_file():
            out.append(p)
    return out


def iter_build_files(root: Path) -> list[Path]:
    out: list[Path] = list(iter_dest_build_files(root))
    for base in (
        root / ".." / ".derived" / "legacy-at-3",
        Path("/projects/.derived/legacy-at-3"),
        root.parent / ".derived" / "legacy-at-3",
    ):
        for name in BUILD_NAMES:
            p = (base / name).resolve()
            if p.is_file() and p not in out:
                out.append(p)
    return out


def generator_plugins(root: Path, *, dest_only: bool = False) -> list[dict]:
    plugins: list[dict] = []
    seen: set[str] = set()
    files = iter_dest_build_files(root) if dest_only else iter_build_files(root)
    for path in files:
        for rec in parse_generator_plugins(_read_build(path)):
            rec = dict(rec)
            rec["build_file"] = str(path)
            key = (
                rec.get("artifactId") or "",
                tuple(rec.get("input_specs") or []),
                tuple(rec.get("packages") or []),
                rec.get("build_file") or "",
            )
            if key in seen:
                continue
            seen.add(key)
            plugins.append(rec)
    return plugins


def build_declares_generator(root: Path) -> bool:
    return bool(generator_plugins(root))


def generator_input_paths(root: Path, *, dest_only: bool = False) -> dict[str, list[str]]:
    """Dest-relative spec paths + build file names the plan must own."""
    specs: list[str] = []
    seen: set[str] = set()
    for rec in generator_plugins(root, dest_only=dest_only):
        for spec in rec.get("input_specs") or []:
            s = spec
            if not s:
                continue
            if s not in seen:
                seen.add(s)
                specs.append(s)
    if (root / "build.gradle.kts").is_file():
        builds = ["build.gradle.kts"]
    elif (root / "build.gradle").is_file():
        builds = ["build.gradle"]
    else:
        builds = ["pom.xml"]
    return {"specs": specs, "builds": builds}


def fqcn_from_src_rel(rel: str) -> str:
    p = _rel_posix(rel)
    for marker in ("src/main/java/", "src/test/java/"):
        idx = p.find(marker)
        if idx >= 0:
            body = p[idx + len(marker) :]
            if body.endswith(".java"):
                body = body[: -len(".java")]
            return body.replace("/", ".")
    return ""


def _legacy_roots(root: Path) -> list[Path]:
    out: list[Path] = []
    for cand in (
        (root / ".." / ".derived" / "legacy-at-3").resolve(),
        Path("/projects/.derived/legacy-at-3"),
        (root.parent / ".derived" / "legacy-at-3").resolve(),
    ):
        if cand.is_dir() and cand not in out:
            out.append(cand)
    return out


def find_generated_basename(root: Path, basename: str) -> Path | None:
    if not basename.endswith(".java"):
        basename = basename + ".java"
    hits: list[Path] = []
    for base in _legacy_roots(root):
        gen = base / GENERATED_DIR
        if not gen.is_dir():
            continue
        hits.extend(p for p in gen.rglob(basename) if p.is_file())
    dest_gen = root / GENERATED_DIR
    if dest_gen.is_dir():
        hits.extend(p for p in dest_gen.rglob(basename) if p.is_file())
    uniq = []
    seen: set[str] = set()
    for h in hits:
        try:
            k = str(h.resolve())
        except OSError:
            continue
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    if len(uniq) == 1:
        return uniq[0]
    return None


def _in_generator_package(fqcn: str, plugins: list[dict]) -> bool:
    if not fqcn:
        return False
    for rec in plugins:
        for pkg in rec.get("packages") or []:
            p = pkg.strip().rstrip(".")
            if not p:
                continue
            if fqcn == p or fqcn.startswith(p + "."):
                return True
    return False


def _in_src_tree(root: Path, rel: str, source: Path | None) -> bool:
    if source is not None and source.is_file():
        sp = str(source).replace("\\", "/")
        if path_is_generated(sp):
            return False
        if "/src/main/java/" in sp or "/src/test/java/" in sp:
            return True
    rel_n = _rel_posix(rel)
    if path_is_generated(rel_n):
        return False
    dest = root / rel_n
    if dest.is_file():
        return True
    for base in _legacy_roots(root):
        cand = base / rel_n
        if cand.is_file():
            return True
    return False


def is_generated(
    root: Path,
    dest_rel: str,
    *,
    source: Path | None = None,
    legacy_rel: str | None = None,
) -> bool:
    """True when dest_rel (or source file) is generator output, not source."""
    rel_n = _rel_posix(dest_rel)
    if path_is_generated(rel_n):
        return True
    if source is not None:
        if path_is_generated(source) or file_has_generated_annotation(source):
            return True
    dest_p = root / rel_n
    if dest_p.is_file() and file_has_generated_annotation(dest_p):
        return True
    for base in _legacy_roots(root):
        cand = base / rel_n
        if cand.is_file() and (
            path_is_generated(cand) or file_has_generated_annotation(cand)
        ):
            return True
        if legacy_rel:
            lcand = base / _rel_posix(legacy_rel)
            if lcand.is_file() and (
                path_is_generated(lcand) or file_has_generated_annotation(lcand)
            ):
                return True
    plugins = generator_plugins(root)
    basename = Path(rel_n).name
    hit = find_generated_basename(root, basename)
    if hit is not None:
        return True
    if not plugins:
        return False
    if _in_src_tree(root, rel_n, source):
        return False
    fqcn = fqcn_from_src_rel(rel_n)
    lq = fqcn_from_src_rel(legacy_rel or "")
    if _in_generator_package(fqcn, plugins) or _in_generator_package(lq, plugins):
        return True
    return False


def inventory_row_is_generated(root: Path, rec: dict) -> bool:
    """Classify a type-inventory row from path / @Generated / plugin — not the stored boolean."""
    dest = str(rec.get("dest_file") or rec.get("file") or "").strip()
    if not dest:
        return False
    src = rec.get("source_file") or rec.get("legacy_file")
    source = Path(str(src)) if src else None
    legacy = str(rec.get("legacy_file") or rec.get("source_file") or "") or None
    return is_generated(root, dest, source=source, legacy_rel=legacy)
