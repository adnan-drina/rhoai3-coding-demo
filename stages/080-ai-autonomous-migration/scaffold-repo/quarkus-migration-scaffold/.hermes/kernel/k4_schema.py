"""K4 mint converter schema (AD-019 §4 K4). Not a skill. Not dest-apply.

Write-set source is the typed partition row. PATH_TOKEN over tasks.md is
OBJECT. Does not import create_task. Does not shell hermes kanban.
Does not read type-inventory reached_from (partition files_writable only).
"""
from __future__ import annotations

WRITER_ID = "mint-writer"
VERIFIER_ID = "mint-verifier"
STAMP_ID = "STAMP_DESTINATION_TREE"
STAMP_SKILL = "commit-destination-tree"
ORCH = "orchestrator"
IMPL = "implementer"
PATH_TOKEN_MARKERS = ("PATH_TOKEN",)
SHA256_RE = r"^[0-9a-f]{64}$"

REMEDY = {
    "K4_SCHEMA": (
        "Partition needs type_inventory_sha256 (64 hex) and stories[] with "
        "story_id, files_writable[], and parents[] from the import graph. "
        "Do not import create_task."
    ),
    "K4_PATH_TOKEN": (
        "Do not scrape write-sets from tasks.md. Copy files_writable from the "
        "typed partition row for that logical story_id."
    ),
    "K4_SCOPE": (
        "M3 payloads need non-empty files_writable copied from the partition. "
        "Acceptance that needs pom.xml (health / add-extension) or a proves "
        "path must list those files in files_writable; otherwise the story "
        "is unsatisfiable (kanban_block, do not mint). The harvest card "
        "STAMP_DESTINATION_TREE needs a non-empty union of those product "
        "writes after OBJECT filter (evidence/, .hermes/, .specify/, "
        "target/, .env). Do not stamp mvn test-compile as an exit "
        "(empty test tree always passes)."
    ),
    "K4_CREATED_CARDS": (
        "Manifest created_cards must be the exact non-empty payload logical_id "
        "list in create order ([] skips — forbid). Worker maps those to Hermes "
        "t_* after kanban_create."
    ),
    "K4_PLANNING_DEFECT": (
        "A path named in tasks.md but absent from the partition is a planning "
        "defect. Report every such path. Do not grow the write-set from prose."
    ),
    "K4_FACTORY": (
        "Dest mint-writer and mint-verifier LLM cards are retired "
        "(Architect 164714ZA; native-kanban-alignment 13–14). M2 runs "
        "k4_mint.py as CLI translation. Do not emit those payloads."
    ),
    "K4_ASSIGNEE": "M3 assignee=implementer. Dest factory cards are not minted.",
    "K4_PARENT": (
        "M3 parents come from the partition import-graph. The stamp card "
        "parents every M3 story. The M2 card (HERMES_KANBAN_TASK) is an "
        "extra parent at mint time. Dest mint-verifier is not a parent."
    ),
    "K4_T0_3_SERVICE": (
        "T0_3_SERVICE is write-set legality only: the same *Service.java must "
        "not appear in two stories' files_writable. One story MAY own a shared "
        "facade. Wrong reading: methods in a shared ClinicService on six "
        "stories (v42). Split-one-class-per-aggregate is architecture "
        "(petclinic ADR), not this mint refuse."
    ),
    "K4_MINT_CREATE": (
        "Mint argv is hermes kanban create with inline --body. Do not import "
        "create_task. Do not kanban swarm. Do not kanban decompose. Do not "
        "kanban daemon --force."
    ),
    "K4_MINT_TITLE": (
        "Story titles are exactly 'M3 <logical_id>'. Dest factory titles "
        "are not minted."
    ),
    "K4_MINT_RETRIES": (
        "M3 story creates pass --max-retries 1 (CLI). "
        "The model kanban_create tool has no max_retries field."
    ),
    "K4_MINT_PARENT": (
        "Resolve payload parents from already-minted logical_id → t_* in "
        "create order. M4 VERIFY parents are those minted M3 t_*. Do not "
        "invent parents. Do not mint dest factory cards."
    ),
    "K4_MINT_ID": (
        "Parse create --json for task_id or id (t_*). Serialize creates; "
        "do not mint in parallel. --exec output created_cards is those t_* "
        "ids (Architect 144916ZA: empty after a mint is OBJECT)."
    ),
    "K4_MINT_SKILLS": (
        "M3 story creates pass --skill for every pinned leaf. An empty "
        "skills list is REFUSE (dest-5 T001 loaded 11 by skill_view)."
    ),
    "K4_MINT_WORKSPACE": (
        "M3 story creates pass --workspace dir:/projects/modernized or a "
        "path under that tree. K4_WORKSPACE or MODERNIZED_ROOT that is "
        "empty, relative, or outside the modernized tree is REFUSE "
        "(scratch OBJECT). Mint always emits the flag after this check; "
        "omission is not a path."
    ),
    "K4_MINT_RUNTIME": (
        "Every mint passes --max-runtime (default 2h) so the dispatcher "
        "SIGTERM+requeues instead of a hand-polled stall."
    ),
    "K4_SKILLS": (
        "Partition story.skills[] or kind (setup/us/polish/database) must "
        "yield a non-empty skill list before mint."
    ),
    "K4_NO_PRODUCER": (
        "Every M-stage card must pin a skill that owns producing its primary "
        "artifact (Architect 143941ZA). Checkers (check-*, assert-*) do not "
        "count. M2 card pins paved-road-m2; producer of partition.json is "
        "plan-migration-partition (skill_view). M4 pins compose-m4-verdict. "
        "M3 setup pins author-destination-pom; US pins "
        "spring-to-quarkus-patterns; database pins form-entity-persistence "
        "(dest-k8s); STAMP pins commit-destination-tree. dest-8 M2 and M4 "
        "failed this bar."
    ),
    "K4_LEGACY_SOURCE": (
        "HTTP stories must set legacy_source to the inventory file "
        "(entry-point-inventory.json `file`) so the M3 body names the "
        "legacy package. dest write-set is the dest package; do not make "
        "the worker rediscover com/example/restservice from com/demo."
    ),
    "K4_DEST_FILE": (
        "HTTP stories must set dest_file to the type-inventory dest twin of an "
        "inventoried legacy type, not the new file this story creates. "
        "Absence is skip in dest_file_invented, so dest-9 live us1_greeting "
        "(Application.java / GreetingResource.java in files_writable, "
        "dest_file missing) never REFUSEd invented dest Java. Convert "
        "refuses missing dest_file on HTTP; do not rewrite that skip."
    ),
}
