# Local metering corrections: 2026-10-19

The corrected Noyitz backend was rebuilt and validated locally. **115 top-level
Go tests passed** (201 including subtests), with no failed or skipped tests.
The runtime probe recorded **93 passing checks** and two observed limitations.
Three Go packages contain no tests; their package-level skip records are not
skipped test cases. See [summary.json](summary.json) for machine-readable results.

No cluster was contacted, no image was published and nothing was deployed.
Owned local test containers, the database volume, internal network and aborted
build-storage container were removed. The Podman VM is stopped; unrelated
containers remain stopped. The [original evidence](../noyitz-local-20261018/README.md)
is unchanged and its checksum manifest was rechecked.

## Artifact identity

| Input or artifact | Identity |
| --- | --- |
| Upstream source | `f9a56b1769b0933e3fe7454a174b1f42a229f07a` |
| Correction patch SHA-256 | `c997048addb0afbfe25d38eb8de5ec06dca2d08e7f3414d3593737480c385a1e` |
| Local image | `localhost/showback-metering:f9a56b1-c997048addb0` |
| Image config ID | `sha256:34bf73af2c838edb000d18915b42bb5d9fbb98c97f7c9e5962b8ef7b8b8616d9` |
| Exported OCI manifest | `sha256:ff3eb4b2759460150c35b3622ee8ef2668c75ff95b62f78bf1d53cfc99820931` |
| Target | Linux amd64, Go 1.26.0, runtime UID 1001 |
| Local database | Digest-pinned PostgreSQL 16.15 ARM64, unpublished on an internal network |

The [build records](build/build.json) bind the clean source archive, exact patch,
pinned Containerfile, compiler and image labels. The patch requires PostgreSQL
15+ for its uniqueness index. The [build helper](../../backend/build-local.sh)
and [probe](../../test-backend-local.sh) are Bash; the patch modifies the existing
upstream Go service. The local OCI archive is retained at the Git-ignored path
`tmp/showback-noyitz-local-20261019/metering.oci.tar`. Its checksum and the matching
builder/runtime binary checksums are recorded here. None of these identifiers
is a published registry digest.

The Go tests used the cached pinned compiler/module image with the **final patched
build context mounted read-only**; they did not test its old embedded source.
[go-test-command.json](go-test-command.json) records this distinction. The runtime
probe then exercised the newly built image itself.

## What the tests establish

- Identical source/ID delivery, JSON key reordering, eight concurrent HTTP
  deliveries and replay after restart leave usage, quota, cost and rollups unchanged.
  Storage tests additionally cover concurrent conflicts and rollback/retry.
- A changed payload under the same source/ID returns 409. A different source is
  independent. Missing, invalid, ambiguous and inconsistent usage returns 400
  without new ledger rows or quota consumption.
- Explicit zero usage stays complete. Native errors without usage retain the
  complete semantic JSON, `usage_complete=false` and NULL cost. Database tests
  verify that backfill, rollup rebuilding and reopening preserve this distinction.
- Legacy duplicates block migration without deleting history. Legacy completeness
  stays unknown; an old row without its original payload cannot prove a replay.
- With PostgreSQL stopped, both health endpoints return 503; after restart they
  return 200. Ingestion fails during the outage, then succeeds exactly once when
  retried and replayed. The final synthetic run contains eight request/audit rows
  and 1,380 tokens, with per-user raw/rollup parity.

The two observed limitations are intentional boundaries: quota-denial audits
increase request counts, and numeric rollups show known subtotals without
completeness. The native dashboard is still unsuitable as the financial authority.
Fallback pricing, provider-category normalization, IPP delivery/retry, stream
completion, user isolation, export and invoice reconciliation remain separate
qualification work. The shell showback accountant retains its existing role.

## Evidence and attempts

- `first-build/`: failed build inputs and log. The local VM stopped during
  compilation and the connection ended with unexpected EOF; the cause was not
  established. The original attempt is retained. The final reviewed patch was
  rebuilt with compiler parallelism bounded to two.
- `build/`, `binary-*`, `oci-*`: accepted build, source/patch/recipe identities,
  compiler metadata, binary checksums and exact exported OCI metadata.
- `go-test.jsonl`, `go-test-result.json`: complete test stream and derived counts;
  `go-test.exit` is zero. Both database environment variables were supplied using
  throwaway private files; their values are not retained.
- `runtime/`: exact probe source/hash, results, checks and selected SQL snapshots.
  `captures.jsonl` losslessly packs 448 additional UTF-8 files as
  `{path,sha256,content}` records. Write each content string without adding a newline
  to reconstruct a file, and verify its SHA-256.
- `cleanup/`: removal receipts, final resource inventories, stopped VM state and
  credential-file cleanup. An unsupported remote cleanup option was corrected;
  its note is retained. Original images and evidence were preserved.

From this directory, `shasum -a 256 -c SHA256SUMS` verifies the retained bundle.
For reproduction, use a new disposable database and evidence directory; never
rewrite this historical run. No cluster rollback is needed. Review the
[patch migration and rollback notes](../../backend/README.md) before any later
activation proposal.
