# Agent runtime images

The OpenCode and Hermes sandboxes run images built in the cluster by the two binary BuildConfigs that
`060-openshell-runtime` owns in `ai-agents` (`images/` and `hermes-images/` in its GitOps folder). Builds are started by
hand, never by triggers. The sandbox templates (`../sandboxes/*/template.json`) pin the resulting digests; a new build
does not change a running sandbox until a reviewed template change uses its digest.

| Script | When to run |
|---|---|
| `build-opencode.sh` | After a reviewed change of `opencode/` (release version, asset checksum or Dockerfile). Downloads the official release asset, checks its SHA-256 and that it holds exactly one `opencode` binary, builds `opencode-runtime:1.18.16` and prints the immutable image reference. |
| `build-hermes.sh` | After a reviewed change of `hermes-api/` (base image, dependency closure or packaging check). Downloads the hash-locked wheels from `dependency-source.json`, checks each SHA-256, builds `hermes-runtime-api:0.20.5-api` and prints the immutable image reference. |

Both scripts build only a published revision: `RHOAI_STAGE060_EXPECTED_REVISION` (default `HEAD`) must be on `origin`,
this checkout's build inputs must equal it, and `060-openshell-runtime` must be synced at it. Each run starts one
OpenShift Build and changes nothing else; rerunning builds the same input again.

Build contexts:

- `opencode/`: `Dockerfile` (UBI 9 plus the release binary) and `release-source.json` (asset URL, SHA-256, source commit).
- `hermes-api/`: `Dockerfile` (the Stage 130 Hermes workspace image plus the native HTTP dependency closure),
  `requirements.lock`, `dependency-source.json` and `verify-packaging.py`, which runs inside the image during the build
  (before and after the wheel install) to prove the fork, the existing packages and the private interpreter are
  unchanged.
