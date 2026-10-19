# Noyitz local build and validation — 2026-10-18

**The pinned image built successfully and the specified local tests passed.** Nothing was published,
deployed to OpenShift or connected to MaaS. All temporary containers, their database volume and network
were removed; the initially stopped Podman VM is stopped again. The image and local OCI archive remain.

[summary.json](summary.json) is the machine-readable record. [SHA256SUMS](SHA256SUMS) binds the retained
evidence files. This is local synthetic validation of a community development backend, not Red Hat
product support, gateway qualification or complete financial accounting.

## Artifact

| Item | Recorded value |
|---|---|
| Source | [Noyitz f9a56b1769b0933e3fe7454a174b1f42a229f07a](https://github.com/noyitz/ai-gateway-metering-service/tree/f9a56b1769b0933e3fe7454a174b1f42a229f07a), clean checkout; no source patch |
| Build | Linux AMD64, Go 1.26.0, CGO disabled, runtime UID 1001; ARM64 Podman VM using QEMU |
| Bases | Go 1.25 Alpine and UBI 9.5 minimal pinned to AMD64 manifests in [Containerfile.pinned](Containerfile.pinned) |
| Local image | `localhost/showback-metering:f9a56b1769b0933e3fe7454a174b1f42a229f07a` |
| Image/config ID | `sha256:a1dacdd86d72736e82b4e126a506940cc44b64dd5734a1d8ac37dd538aeed7a9` |
| Exported OCI manifest | `sha256:c96ead9bccfe344f49b27628016fed20d843b1e0ebc816878c6ce214785d2b00` |
| Local archive | Repository-relative `tmp/showback-noyitz-local-20261018/metering.oci.tar` (ignored by Git, 44 MiB) |
| Archive SHA-256 | `0ee980daa8d4bcbf9c7bf0ffa03e312e27581886b24f06fb7d83127d08aef333` |

The local storage manifest, exported OCI manifest, config ID and archive checksum are different
identifiers. None is a published registry digest. Inherited UBI vendor labels describe the base image;
they do not turn this community binary into a Red Hat metering product. The final image's binary hash
matches the builder binary whose [build information](binary-buildinfo.txt) confirms Go 1.26.0.

## Checks and retained attempts

| Check | Result / evidence |
|---|---|
| Pinned build | Exit 0; [build log](build.log), original and derived Dockerfiles, source/dependency hashes |
| Upstream tests | **96 top-level tests passed**, 123 including subtests, zero failed or skipped tests; [result](upstream-result.json), [raw Go events](upstream-tests.jsonl). Two packages contain no tests. Both database DSNs were supplied, so database integration and SQL preflight actually ran. |
| Local API/database | **27 passed assertions + 7 observed-limitations assertions**; [accepted result](runtime-retry/result.json). Synthetic identity/tokens persist, balances change, a separate user exceeds quota, malformed requests are rejected, dashboard requests require a session, and backend restart preserves rows/rollups/balances. |
| Database outage/recovery | [Result](database-recovery/result.json): health/readiness remain 200, entitlement returns 500; after database restart, entitlement returns 200 and the same-volume rows/rollups are unchanged. |
| Repository checks | Bash syntax, native contract suite and inert render check passed; stopped-bundle checks: 5 passed, 0 failed. |
| Cleanup | [Final VM state](machine-final.json), [empty local container inventory](containers-after-cleanup.json), removal receipts. Unrelated rootful containers remained stopped. Private test environment files were deleted. |

Two unsuccessful attempts remain visible:

1. The initial upstream-test launcher refused toolchain verification with `GOSUMDB=off`
   ([stderr](upstream-launch-attempt1.stderr)); no tests ran. The successful invocation used the same
   downloaded Go 1.26.0 executable directly with `GOTOOLCHAIN=local`, preserving disabled network retrieval.
2. The first API probe incorrectly expected four ledger rows. Its [failed result](runtime/result.json)
   and raw data are preserved. A denied entitlement check also creates an asynchronous zero-token audit
   row. The [probe correction](probe-correction.patch) explicitly verifies four submitted events plus
   one audit row, five ledger/rollup requests and 1,340 tokens. The successful run used fresh identities.

Each runtime directory's `capture.jsonl` stores the original filenames, SHA-256 and exact UTF-8 content
of every HTTP/SQL/result file. Packing verified every content hash; important results and snapshots also
remain separate. Original failed outputs were not rewritten. The summary binds each attempt to its
probe-script hash; reversing `probe-correction.patch` against the accepted script reconstructs the first
script. Exact script snapshots also remain in ignored `tmp/showback-noyitz-local-20261018/`.

## Limits that matter for showback

- Identical source/event-ID replay is counted twice and consumes quota twice.
- Omitted token fields are accepted and stored as zero; they do not prove zero consumption.
- A denied balance GET writes a stored 429 audit row, although its actual HTTP response is 200 with
  `hasAccess=false`. Request totals include those checks; no gateway HTTP 429 was tested here.
- `/health` and `/ready` do not detect a database outage. Balance errors do not establish IPP delivery
  recovery or gateway fail-open behavior.
- The isolated network blocked startup price downloads, selecting bundled prices. The unknown synthetic
  model still received a fallback dollar cost. These amounts are not our agreed service-offer prices.

The PostgreSQL 16.15 container had no host port. The backend was exposed only on `127.0.0.1`; no provider
credentials, kubeconfig, real users, model requests or gateway traffic were used. Identity assertions
cover stored user/model/source and base token fields; retained rows also preserve the submitted
group/subscription/provider/user-agent fields. This is not proof of trusted gateway identity delivery.

Reproduce with the [local build/validation procedure](../../../OPERATIONS.md#obtain-or-build-the-reference-backend-image)
and [Bash API probe](../../test-backend-local.sh), using a fresh disposable database and evidence directory.
The exact upstream command/environment is in `upstream-result.json`. Review replay/missing-usage,
pricing, raw-event retention, authenticated access, streaming and failure recovery before any later
gateway activation. The existing shell accountant remains the financial authority.
