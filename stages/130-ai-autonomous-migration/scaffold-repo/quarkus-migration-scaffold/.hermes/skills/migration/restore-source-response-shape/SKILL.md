---
name: restore-source-response-shape
description: >
  Use on a PARITY_CORS or PARITY_CONTENT_TYPE card (ADR-019) to install the
  harness's source-preserving response adapter with install-response-adapter.py.
  CORS: a route-level adapter that reaches the platform's early preflight
  answer, with every permission rendered from the frozen source's own CORS
  policy. Content-Type: a separate adapter that removes only the decided
  media-type parameter. Not for hand-written filters, restored @CrossOrigin,
  configuration-only CORS repairs, or comparator changes.
license: Apache-2.0
compatibility: Linux seat; Python 3.9+; Quarkus (RHBQ 3.27) vertx-http route filters; a JDK and Maven for runtime-check.sh
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - parity
    - cors
    category: migration
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/structure/structure.json", "/projects/modernized/evidence/planning/worklist.json", "/projects/modernized/verification/loop/issued.json"]
      writes: ["/projects/modernized/src/main/java/io/rhoai3/migration/response", "/projects/modernized/src/main/resources/application.properties", "/projects/modernized/evidence/response-adapters"]
---
# Restore the source's response shape (ADR-019)

The architect's third review (ADR-019): **CORS is repaired by a
source-preserving response adapter**, a reusable harness capability; a
Content-Type charset difference is **a separate response-representation
obligation**. This skill is that capability. A worker installs it. A worker
does not write it, edit it or copy it.

## When to Use

- The card's items carry `rule_id: PARITY_CORS` (cause `cors-response`) and an
  `owed` row naming `source-cors-response-adapter/v1`.
- The card's items carry `rule_id: PARITY_CONTENT_TYPE` (cause
  `content-type-parameter`) and an `owed` row naming
  `source-media-type-parameter-adapter/v1`. First check whether a response or
  serializer setting makes the destination send the source's Content-Type; the
  adapter is the fallback.
- **Not** to restore `@CrossOrigin`, write your own filter, set only
  `quarkus.http.cors.*`, widen a policy until a capture passes, or normalize
  the comparison.
- **Not** on a CORS card for a Content-Type change (or the reverse): each
  obligation authorizes only its own adapter.

## Steps

1. Read the brief. The card's sealed write set already holds the adapter path
   and `src/main/resources/application.properties`; the unit's
   `implementation` row names the contract, type, path, template digest and
   the rows the harness rendered.
2. Install:

   ```bash
   python3 .hermes/skills/migration/restore-source-response-shape/scripts/install-response-adapter.py --root . --adapter cors
   python3 .hermes/skills/migration/restore-source-response-shape/scripts/install-response-adapter.py --root . --adapter media-type
   ```

   `--print` shows the rendering without writing. The installer refuses
   (`REFUSE: <CODE>`) when no obligation authorizes it, when the issued card
   does not hold both paths, when the adapter path holds other content, or when
   a profile-scoped row of the capability's own key family exists.
3. Verify the installation, then run the card's acceptance as usual:

   ```bash
   python3 .hermes/skills/migration/restore-source-response-shape/scripts/install-response-adapter.py --root . --adapter cors --check
   bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance
   ```

   The card is discharged by its own parity scenarios coming back PASS on the
   packaged artifact, with no scenario that was PASS regressing, and by
   `assess_unit` finding the template bytes, the contract type and every
   rendered row in place.

## What the CORS adapter does

- **Where:** a Vert.x route filter registered above the platform's CORS
  filter (`SecurityHandlerPriorities.CORS + 100`). The platform ends a
  preflight in its own filter, before authentication and before any endpoint;
  a response filter behind it never sees that answer.
- **Permissions come from the source policy**, rendered by the installer from
  M1's structural model: each `@CrossOrigin` (class and method level, with
  Spring's documented defaults), the handler mappings it covers, and whether
  the source's security configuration ran before its CORS processing (no
  `cors()` call) and under which switch value it refused anonymous requests.
  Captures decide only what a response must look like.
- **Platform rows** (`quarkus.http.cors.*`) are the union of what the source
  grants. **Adapter rows** (`rhoai3.source-cors.*`) narrow every response to
  its handler's policy: the source's `Access-Control-Allow-Origin` value, only
  that handler's methods, only the requested headers the policy allows, the
  source's max-age, exposure on the source's responses, and no credentials
  header unless the source sent one.
- **Never widens:** a response the platform did not grant leaves with no CORS
  header and an unchanged status. An origin, method or header set the source
  policy refuses gets `403 Invalid CORS request`. With security first in the
  source, that refusal happens after authentication. A route outside every
  source policy gets no CORS header.
- **Untouched:** requests without `Origin`. Same-origin requests are not CORS
  requests for the source either (ADR-020). The platform's CORS filter does
  not judge them, so a method outside its list is not a 403. They reach
  ordinary routing exactly as they would without `Origin` (a 405 stays a
  405), `Origin` is restored for the application, and they leave without CORS
  headers.
  `Content-Type` is never read or written.
- **Both security modes:** while the source's switch has the value under which
  it refused anonymous requests, a preflight is authenticated like any other
  request (401 without CORS headers when anonymous), and every 401 leaves
  without CORS headers.

## What the media-type adapter does

It removes exactly one parameter (`name=value`, as the recorded differences
decided) from responses of exactly the recorded media types under the
application root. It leaves every other parameter, every other media type and
the body alone. The decision is refused (`MEDIA_TYPE_UNDECIDED`) when the
differences add more than one parameter, disagree on its value, or show the
source sending a parameter the destination does not send.

## Evidence

| Script | Proves |
|---|---|
| `scripts/install-response-adapter.test.py` | rendering from the source model (restrictive fixtures, method-level policies, renamed specimen, refusals), installer authority, conflicts, profile refusal, idempotency, the media-type decision, the templates' structural facts |
| `scripts/runtime-check.sh` | **real runtime**: installs both adapters into `fixtures/runtime` through the installer and runs its `@QuarkusTest` suite (24 cases) with the pinned platform: source-shaped preflight and paired actual responses, restrictive-policy refusals, no blind echo, no-Origin requests untouched, same-origin requests routed exactly as without Origin (an unmapped method is the routing's own 405, where the platform alone answers 403), no permission outside the source policy, both security modes including the mechanism's own 401 challenge and post-authentication 403, the media-type parameter removed and nothing else. It also runs a control where the adapter sits below the platform CORS filter; that control must fail the preflight case. |

`runtime-check.sh` runs Maven offline by default (`--online` to resolve).
The planner half, meaning obligation typing, the sealed `unit/owed-adapter/v1`
write set and the checkpoint assessment, is covered by
`.hermes/lib/planner/worklist.test.py` (`_owed_adapter_case`) and
`fix-until-green/scripts/amend-scope.test.py` (`_owed_adapter_case`).

## Refused

- Comparator normalization or altered source expectations.
- A wildcard policy inferred from one passing capture.
- Header rewriting that turns a rejected exchange into an allowed one.
- Copying the isolated experiment's filter (it stripped every Content-Type
  parameter before it even looked at `Origin`).
- Dropping all Content-Type parameters to obtain a pass.
