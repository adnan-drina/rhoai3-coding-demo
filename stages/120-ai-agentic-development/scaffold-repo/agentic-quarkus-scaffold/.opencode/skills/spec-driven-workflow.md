# Skill: Spec-driven workflow

How to execute the `/speckit.*` workflow in this project. Consult before
running any `/speckit` command.

## Command order

`/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.
The human reviews each artifact before the next command amplifies it — stop
after each command and let them review; do not chain commands yourself.

**Phase discipline**: each command writes **only its own artifacts** and
nothing else. Specify, plan, and tasks never create or modify anything
under `src/` — writing implementation code before `/speckit.implement`
skips the human review gates and is a defect even if the code is
correct. If a phase is interrupted (errors, rate limits), resume the
same phase; do not skip ahead.

## Artifacts each phase must produce

A `/speckit` command is complete only when every artifact below exists.
Do not end your turn before they are all written; if unsure, list the
feature directory and verify before finishing.

- **specify**: `specs/<n>-<feature>/spec.md` and
  `checklists/requirements.md`.
- **plan**: `plan.md` **and** its supporting documents — `research.md`,
  `data-model.md`, `quickstart.md`, `contracts/` with the API contract.
  A filled `plan.md` alone is not a completed plan phase.
- **tasks**: `tasks.md` with ordered, individually verifiable items —
  task IDs strictly sequential and unique (renumber after inserting);
  tests are first-class tasks, not an afterthought. Test-infrastructure
  tasks (mock fixtures, test resources) name the exact class and file
  they create and are ordered **before** the test tasks that depend on
  them — "add mock setup in test resources" is not a verifiable task. **Every
  acceptance path named in the spec maps to at least one named test
  task** (happy path, unknown-item, degradation, …) — an acceptance
  path with no test task is an incomplete list. When the spec requires
  tests to pass without a live downstream service, the mocking fixture
  (its class and its dependency) are mandatory tasks — a task list
  whose happy-path test cannot pass offline is a defect. Every library
  any task uses (runtime or test — REST client, WireMock, …) must have
  an explicit setup task adding its `pom.xml` dependency; a task list
  that references a library nothing installs will fail at implement
  time.
- **implement**: source and tests per `tasks.md`, then `mvn -q test`
  green, then a gate-hygiene pass over every touched file (unused
  imports, dead code, field injection — the pipeline gate fails on any
  new issue) before reporting done. Execute one task at a time in
  order, and tick its checkbox in `tasks.md` immediately after its
  verification passes — never batch checkbox updates at the end. If a
  session is interrupted, the checkboxes are the source of truth: on
  resume, reconcile them against the actual file tree before writing
  any code.

## Writing specs (specify phase)

Describe user scenarios, business rules, constraints, and observable
behavior in plain language. Seed data and API paths given in a brief are
the contract — copy them exactly; never round, substitute, or invent
values. Do not choose the tech stack or write implementation detail in a
spec — that belongs to the plan, which is steered by the constitution
and the other skills in `.opencode/skills/`.

## Completion report

End every `/speckit` command with a short completion report listing the
artifacts written (paths) and the recommended next command.
