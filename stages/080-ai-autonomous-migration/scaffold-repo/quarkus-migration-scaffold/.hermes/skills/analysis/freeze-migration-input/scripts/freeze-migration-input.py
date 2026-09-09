#!/usr/bin/env python3
"""Freeze the original legacy source into a content-addressed manifest.

Writes evidence/frozen/source-manifest.json and evidence/producers/freeze.json.
Optionally makes a byte-identical analysis copy (--copy-to) and verifies it.

Exit 0 ok; 1 FREEZE_* refusal; 2 usage.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import canonical_bytes, sha256_bytes, sha256_file, write_canonical  # noqa: E402
from planner.paths import SOURCE_MANIFEST, producer_receipt  # noqa: E402

SCHEMA = "rhoai3.source-manifest/v1"
SKIP_DIRS = frozenset({".git", "target", "build", "node_modules", ".idea", ".vscode", ".derived", ".gradle"})


def walk(source: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(source)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append({"path": rel.as_posix(), "sha256": sha256_file(path)})
    out.sort(key=lambda r: r["path"])
    return out


def manifest_digest(files: list[dict[str, str]]) -> str:
    return sha256_bytes(canonical_bytes({"files": files}))


def copy_verified(source: Path, dest: Path, files: list[dict[str, str]]) -> list[str]:
    """Byte-identical copy of the manifest files. Returns mismatches."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for row in files:
        src = source / row["path"]
        dst = dest / row["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    bad: list[str] = []
    for row in files:
        if sha256_file(dest / row["path"]) != row["sha256"]:
            bad.append(row["path"])
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="original legacy root (read-only)")
    ap.add_argument("--root", required=True, help="destination root (writes evidence/)")
    ap.add_argument("--copy-to", default="", help="byte-identical analysis copy path")
    args = ap.parse_args(argv)
    source = Path(args.source).resolve()
    root = Path(args.root).resolve()
    if not source.is_dir():
        print("FAIL: FREEZE_SOURCE_MISSING %s is not a directory" % source, file=sys.stderr)
        return 2
    if not root.is_dir():
        print("FAIL: --root %s is not a directory" % root, file=sys.stderr)
        return 2
    files = walk(source)
    if not files:
        print("FAIL: FREEZE_EMPTY %s has no files" % source, file=sys.stderr)
        return 1
    if not any(r["path"].endswith(".java") for r in files):
        print("FAIL: FREEZE_NO_JAVA %s contains no *.java (wrong mount?)" % source, file=sys.stderr)
        return 1
    digest = manifest_digest(files)
    manifest = {
        "schema": SCHEMA,
        "root_kind": "frozen-legacy",
        "source_root": str(source),
        "digest": digest,
        "files": files,
    }
    reasons: list[str] = []
    copy_path = ""
    if args.copy_to:
        dest = Path(args.copy_to).resolve()
        if dest == source or source in dest.parents:
            print("FAIL: FREEZE_COPY_INSIDE_SOURCE --copy-to must not be under the source", file=sys.stderr)
            return 1
        bad = copy_verified(source, dest, files)
        if bad:
            print("FAIL: FREEZE_COPY_MISMATCH %d file(s) differ after copy: %s" % (len(bad), ", ".join(bad[:5])), file=sys.stderr)
            return 1
        copy_path = str(dest)
    manifest_path = root / SOURCE_MANIFEST
    write_canonical(manifest_path, manifest)
    receipt = {
        "schema": "rhoai3.producer-receipt/v1",
        "producer": "freeze",
        "status": "ok",
        "tool": {"name": "freeze-migration-input", "version": "1.0.0", "pin_status": "not-applicable"},
        "inputs": {"source_root": str(source)},
        "outputs": [{"path": str(SOURCE_MANIFEST), "sha256": sha256_file(manifest_path)}],
        "reasons": reasons,
        "source_digest": digest,
        "analysis_copy": copy_path,
        "file_count": len(files),
    }
    write_canonical(producer_receipt(root, "freeze"), receipt)
    print("OK: froze %d files digest=%s%s" % (len(files), digest[:12], (" copy=" + copy_path) if copy_path else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
