"""One home for every planner path (relative to the destination root)."""
from __future__ import annotations

from pathlib import Path

# contracts (golden, sealed by the receipt)
PLANNING_DIR = Path(".hermes") / "planning"
SCHEMAS_DIR = PLANNING_DIR / "schemas"
CATALOGS_DIR = PLANNING_DIR / "catalogs"
MTA_RULES_DIR = PLANNING_DIR / "mta-rules"
PINS = Path(".hermes") / "pins.json"
DECISIONS = Path("decisions.yaml")
MIGRATION = Path("migration.yaml")

# M1 producer outputs
FROZEN_DIR = Path("evidence") / "frozen"
SOURCE_MANIFEST = FROZEN_DIR / "source-manifest.json"
PRODUCERS_DIR = Path("evidence") / "producers"
STRUCTURE = Path("evidence") / "structure" / "structure.json"
ENTRY_POINT_INVENTORY = Path("evidence") / "entry-point-inventory.json"
TYPE_INVENTORY = Path("evidence") / "type-inventory.json"
MTA_FINDINGS = Path("evidence") / "mta-findings.json"
FINDINGS_HANDOFF = Path("evidence") / "findings-handoff.json"
REQUIRED_EXTENSIONS = Path("evidence") / "required-extensions.json"

# planning artifacts (three, in chain order)
PLANNING_OUT = Path("evidence") / "planning"
EVIDENCE_BUNDLE = PLANNING_OUT / "evidence-bundle.json"
WORKLIST = PLANNING_OUT / "worklist.json"
ADMISSION_RECEIPT = PLANNING_OUT / "admission-receipt.json"
BOOTSTRAP_RECEIPT = PRODUCERS_DIR / "bootstrap.json"
BOM_MANAGED = Path("evidence") / "build" / "bom-managed.json"  # probe-bom-managed.py: artifacts the pinned BOM manages
ARTIFACT_KEYS = (
    ("evidence-bundle", EVIDENCE_BUNDLE),
    ("worklist", WORKLIST),
    ("admission-receipt", ADMISSION_RECEIPT),
)

# verification (append-only run records; never mutate a sealed artifact)
VERIFICATION_DIR = Path("verification")
MTA_RESCAN_FINDINGS = VERIFICATION_DIR / "mta-rescan" / "findings.json"
VERIFY_DIR = VERIFICATION_DIR / "build"
VERIFY_DIAGNOSTICS = VERIFY_DIR / "diagnostics.json"
VERIFY_SUREFIRE = VERIFY_DIR / "surefire.json"
VERIFY_RUN = VERIFY_DIR / "run.json"
LOOP_ISSUED = Path("verification") / "loop" / "issued.json"
LOOP_CARDS = Path("verification") / "loop" / "cards.json"
LOOP_ACCEPTED = Path("verification") / "loop" / "accepted"
PARITY_DIR = VERIFICATION_DIR / "parity"
LOOP_DIR = VERIFICATION_DIR / "loop"
LOOP_STEPS = LOOP_DIR / "steps.json"
LOOP_DEFERRED = LOOP_DIR / "deferred.json"
LOOP_STATE = LOOP_DIR / "state.json"

PRODUCER_NAMES = ("freeze", "build", "jdk-model", "mta", "bootstrap")


def producer_receipt(root: Path, name: str) -> Path:
    if name not in PRODUCER_NAMES:
        raise ValueError("unknown producer %r" % name)
    return Path(root) / PRODUCERS_DIR / ("%s.json" % name)


def contract_files(root: Path) -> list[Path]:
    """Every schema, catalog, and rule file the receipt seals (sorted)."""
    root = Path(root)
    out: list[Path] = []
    for sub in (SCHEMAS_DIR, CATALOGS_DIR, MTA_RULES_DIR):
        base = root / sub
        if base.is_dir():
            out.extend(p for p in base.rglob("*") if p.is_file())
    return sorted(out)
