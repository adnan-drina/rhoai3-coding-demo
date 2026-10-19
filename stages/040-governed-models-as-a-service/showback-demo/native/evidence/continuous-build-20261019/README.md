# Continuous metering backend build — 2026-10-19

This is the source-bound local build of the metering-only derivative. It retains
the original Noyitz source pin `f9a56b1769b0933e3fe7454a174b1f42a229f07a`, applies
the unchanged correctness patch and then `0002-continuous-showback.patch`.
Historical build evidence remains unchanged in its original directories.

`build.json`, `image.json` and `Containerfile` bind the Linux amd64 artifact to
the source archive, pinned builder/runtime bases and the composite patch hash:
`5ab927fca0ce6e10bb643de568532a849909ee745a22fea00d4943881eb63cda`.
The local image is `localhost/showback-metering:f9a56b1-5ab927fca0ce`; its config
ID is `87a1e866bafe572f296f75d78b7398a8f7ac43561991e9ef190bafe6135625c9`.
This config ID is not a published registry manifest digest.

`go-tests.json` records successful final-image builder checks for
`internal/storage` and compilation of `cmd` (which has no Go tests). Database
behavior is established separately by the independent runtime cases below.

Build inputs used `--pull=never` and the already cached pinned base images.
The exact build command was `native/backend/build-local.sh --source <clean-pinned-checkout>
--connection podman-machine-default --output <new-private-build-directory> --continuous`.

The final image started against a disposable local PostgreSQL 16 ledger;
`/ready` and `/metrics` returned HTTP 200. Independent synthetic runtime
qualification passed **12 cases with no failures**, retained in
`runtime-qualification.json`: exact conditional estimate arithmetic, replay and
conflict behavior, source/identity/usage validation, unknown versus free zero,
canonical and unmapped identities, context/UTC-month boundaries, always-grant
entitlements, restart persistence, immutable catalogs/frozen history and
database outage recovery. No backend source failures remained.
No provider or OpenShift inference requests were made for the build or these
local checks. `publication.json` separately records the later published image
manifest `sha256:cd5b3dec76e01c9392bea32a4eaad811c7cde3ed5460d2909ee19e5d902cb495`.
Live IPP activation is separate evidence; local runtime qualification and image
publication do not establish it.
