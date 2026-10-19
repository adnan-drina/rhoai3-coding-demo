# Patched local metering backend

This folder carries a small patch to the Noyitz development backend at
`f9a56b1769b0933e3fe7454a174b1f42a229f07a`. It is a community source derivative,
not an RHOAI product operand. No active manifest references this image.
Build and validation entrypoints are Bash; the patch changes the existing Go service.

## Behavior

| Case | Result |
| --- | --- |
| First valid event | Ledger row and hourly rollup commit together; HTTP 204. |
| Same source and ID, same JSON content | HTTP 204 with no additional row, tokens, cost or quota consumption, including concurrent delivery and service restart. JSON key order and whitespace are immaterial. |
| Same source and ID, different content | HTTP 409; the original stays unchanged. Extension fields participate in the comparison. |
| Same ID, different source | Independent event. This does not identify duplicate inferences assigned different IDs by a producer. |
| Successful usage event | All six explicit integer counters are required: prompt, completion, total, cached input, cache creation and reasoning. Null, negative, fractional, oversized or absent values are rejected with HTTP 400. Explicit zeros remain valid; no total or timestamp is invented. |
| Native error event without usage | Retained with `usage_complete=false`, original JSON content and `cost_usd=NULL`. Existing integer token columns hold zero audit sentinels; these are **not measured zero usage**. Partial token sets are rejected. |
| Database unavailable | `/health` and `/ready` run a primary database query with a one-second deadline and return HTTP 503. Ingestion has a two-second database deadline and returns a failure; a later producer retry may succeed. |

The envelope requires CloudEvents 1.0, a supported inference event type, nonempty
source/ID/user/model and a valid explicit RFC3339 timestamp. Duplicate JSON keys,
case variants of known wire fields and totals below prompt plus completion are
rejected; cache and reasoning categories are not added to that lower bound.
Error events require
an HTTP status from 400 through 599. The complete event content is retained in
`raw_event` as JSONB; serialization order and whitespace are not preserved.

The unique source/ID index requires PostgreSQL **15 or later**; local qualification
uses PostgreSQL 16. This is stricter than the upstream README's PostgreSQL 14 minimum.
Migration refuses existing duplicate source/ID history, including NULL sources,
without deleting events. Reconcile that history separately before an upgrade.
A legacy row without raw content cannot prove an identical replay and returns a
conflict. Legacy `usage_complete=NULL` means unknown; existing prices and legacy
backfill estimates are preserved, not newly qualified.

## Local build

Use `build-local.sh` when explicitly authorized to build locally. Supply a clean
checkout at the pinned revision, an already running local Podman connection and
an existing empty output directory. Both digest-pinned base images must already
be present (`--pull=never`). Go module/toolchain downloads need network access on
a cold cache. The helper archives the source, applies the reviewed patch in its
output directory, and builds the runtime and test-builder images. It does not
start a VM, run the backend, push an image or contact OpenShift.

```bash
bash build-local.sh \
  --source /absolute/path/to/clean-pinned-noyitz \
  --connection podman-machine-default \
  --output /absolute/path/to/empty-build-directory
```

The image name includes the source prefix and patch hash. Labels retain the full
source revision and `io.showback.patch.sha256`. `build.json`, logs, the exact patch,
Containerfile, source archive and image metadata bind the local artifact to its
inputs. Containerfile bases and Go 1.26.0 remain pinned to the original build.
Compiler parallelism is bounded to two workers for the local emulated build.

Run [the local probe](../test-backend-local.sh) against a disposable backend and
PostgreSQL on an internal local network, with the backend published only on
loopback and `MONTHLY_TOKEN_QUOTA=1000`. It temporarily stops/restarts the named
database and restarts the backend. Run the patched Go tests with both
`DATABASE_URL` and `PREFLIGHT_DSN` pointing to that disposable migrated database;
database integration tests need permission to create/drop their temporary databases.
Remove owned containers/network/database volume and restore the original VM state.

## Remaining limits and rollback

These changes do not make the native dashboard a complete financial ledger.
Its numeric rollups retain zero arithmetic sentinels for incomplete events, and
its views do not expose completeness. Consult `usage_complete` and original event
content; use this demo's fail-closed importer/accountant for financial statements.
Unknown-model fallback prices, mutable price catalog loading, provider-specific
cache normalization and quota-denial audit request counts remain upstream behavior.

The IPP producer can already emit zeros for absent upstream usage; presence checks
cannot recover that lost distinction. IPP delivery has no durable retry queue.
Database health proves a primary read, not write permission, storage capacity,
complete capture or provider reconciliation. Do not attach these dependency checks
as restart-triggering liveness probes without a separate deployment review.

No rollback is required in the cluster because nothing is deployed. Retain the old
image and evidence. For local revalidation, discard only the explicitly named
disposable database and create a fresh one. Do not roll an existing ledger back to
the unpatched writer or remove its uniqueness index as a workaround: the old writer
cannot handle duplicate conflicts and does not retain the new raw/completeness fields.
