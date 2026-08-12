"""javax→jakarta EE namespace slice — prefer MTA Windup; free-primitive fallback."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import iter_files, record_rule, repo_root, tree_digest  # noqa: E402

RULE_ID = "javax-to-jakarta"
CITE = (
    "MTA/Windup org.jboss.windup.JavaxToJakarta (+ BootstrappingFiles, "
    "PersistenceXML); free-primitive fallback ChangePackage map "
    "(oss-migration-alternatives §1)"
)

# Longer prefixes first. Do NOT map javax.sql or javax.annotation.processing.
PACKAGE_MAP = [
    ("javax.xml.bind", "jakarta.xml.bind"),
    ("javax.websocket", "jakarta.websocket"),
    ("javax.persistence", "jakarta.persistence"),
    ("javax.validation", "jakarta.validation"),
    ("javax.transaction", "jakarta.transaction"),
    ("javax.annotation", "jakarta.annotation"),
    ("javax.inject", "jakarta.inject"),
    ("javax.servlet", "jakarta.servlet"),
    ("javax.ws.rs", "jakarta.ws.rs"),
    ("javax.mail", "jakarta.mail"),
    ("javax.ejb", "jakarta.ejb"),
    ("javax.jms", "jakarta.jms"),
]

POM_ARTIFACT_MAP = [
    ("javax.xml.bind", "jaxb-api", "jakarta.xml.bind", "jakarta.xml.bind-api"),
    ("javax.validation", "validation-api", "jakarta.validation", "jakarta.validation-api"),
    ("javax.annotation", "javax.annotation-api", "jakarta.annotation", "jakarta.annotation-api"),
]


def _needs_jakarta(root: Path) -> bool:
    for path in iter_files(root, (".java", ".xml", ".yml", ".yaml", ".properties")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "javax.annotation.processing" in text:
            text = text.replace("javax.annotation.processing", "")
        for old, _ in PACKAGE_MAP:
            if old in text:
                return True
    return False


def _run_mta(root: Path) -> bool:
    if os.environ.get("SKIP_MTA_JAKARTA") == "1":
        return False
    mta = shutil.which("mta-cli") or shutil.which("kantra")
    if not mta:
        return False
    targets = [
        "org.jboss.windup.JavaxToJakarta",
        "org.jboss.windup.jakarta.javax.BootstrappingFiles",
        "org.jboss.windup.javax-jakarta.PersistenceXML",
    ]
    ok_any = False
    for target in targets:
        cmd = [mta, "transform", "openrewrite", f"--input={root}", f"--target={target}"]
        print(f"[{RULE_ID}] {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=root, check=False)
        if proc.returncode == 0:
            ok_any = True
        else:
            print(f"[{RULE_ID}] warn: mta target {target} exit={proc.returncode}")
    return ok_any


def _fallback_rewrite(root: Path) -> list[str]:
    changed: list[str] = []
    for path in iter_files(root, (".java", ".xml", ".yml", ".yaml", ".properties")):
        text = path.read_text(encoding="utf-8", errors="replace")
        original = text
        # Protect annotation.processing from javax.annotation remap
        text = text.replace(
            "javax.annotation.processing",
            "__JAVAX_ANNOTATION_PROCESSING__",
        )
        for old, new in PACKAGE_MAP:
            text = text.replace(old, new)
        text = text.replace(
            "__JAVAX_ANNOTATION_PROCESSING__",
            "javax.annotation.processing",
        )
        if path.name == "pom.xml":
            for og, oa, ng, na in POM_ARTIFACT_MAP:
                text = text.replace(
                    f"<groupId>{og}</groupId>\n            <artifactId>{oa}</artifactId>",
                    f"<groupId>{ng}</groupId>\n            <artifactId>{na}</artifactId>",
                )
                text = text.replace(f"<groupId>{og}</groupId>", f"<groupId>{ng}</groupId>")
                text = text.replace(f"<artifactId>{oa}</artifactId>", f"<artifactId>{na}</artifactId>")
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    return changed


def main() -> int:
    root = repo_root()
    watch = iter_files(root, (".java", ".xml", ".yml", ".yaml", ".properties", ".pom"))
    pre = tree_digest(watch)
    if not _needs_jakarta(root):
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="precondition false — no EE javax refs",
        )
        print(f"[{RULE_ID}] skip — no EE javax refs")
        return 0

    files: list[str] = []
    notes = ""
    if _run_mta(root):
        notes = "mta-cli transform openrewrite"
        # Capture any residual with fallback (idempotent)
        files = _fallback_rewrite(root)
        if not files:
            # mta may have rewritten in place; list touched by re-scan marker
            files = ["(mta-cli openrewrite targets)"]
    else:
        notes = "fallback ChangePackage map (mta-cli unavailable)"
        files = _fallback_rewrite(root)

    post = tree_digest(watch)
    record_rule(
        rule_id=RULE_ID,
        cite=CITE,
        files=files,
        pre_digest=pre,
        post_digest=post,
        notes=notes,
    )
    print(f"[{RULE_ID}] done files={len(files)} via={notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
