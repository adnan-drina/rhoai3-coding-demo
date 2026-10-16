# Release qualification of the golden scaffold

`qualify-release.sh` qualifies the golden migration scaffold (`../scaffold-repo/quarkus-migration-scaffold`) offline,
before it is published as the golden baseline for new runs ([MIGRATION-IMPROVEMENTS.md](../MIGRATION-IMPROVEMENTS.md),
M-7). It needs no cluster and no model. It runs the scaffold's own Python suites and repeatability driver, so Python 3
is required here (`python3.9`, the workspace interpreter, when installed; otherwise `python3`; `--python` overrides).

| Script | When to run | What it changes |
|---|---|---|
| `qualify-release.sh --out DIR` | Before publishing a scaffold change as the next golden. | Only files under `DIR`: `repeatability.json` and `repeatability.log` from the driver, `suites.txt`, and `verdict.json`. Safe to rerun. |
| `qualify-release.sh --out DIR --suite FILE [--suite FILE ...]` | To rerun selected suites after a fix (paths as listed in `suites.txt`). | The same files. |
| `qualify-release.sh --out DIR --no-suites [--source DIR] [--build-fresh DIR] [--fresh A B] [--patches A B] [--no-producers]` | To run only the repeatability measurement; these options go to `.hermes/skills/planning/build-worklist/scripts/qualify-repeatability.py`. | The same files. |

By default it runs every `*.test.py` and `*selftest*.py` under the scaffold's `.hermes` (fixtures excluded), each with
`--suite-timeout` seconds (default 1800). A suite that needs podman where none is installed, or whose last status line
starts with `SKIP`, is NOT-RUN. `verdict.json` carries the source identity (commit, scaffold tree, dirty flag), every
suite's result, the repeatability cases and the driver's claim grading (MEASURED, PARTIAL, NOT-MEASURED, FAILED).
`verdict` is `PASS` only when the driver produced a report and no suite and no case failed; a NOT-RUN item is listed,
never counted as a pass. Exit 0 PASS, 1 FAIL, 2 wrong arguments.

The run preflight of a created migration workspace is not part of this qualification: it is the live, read-only
`../validate.sh --run`.
