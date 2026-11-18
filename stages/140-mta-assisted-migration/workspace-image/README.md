# Stage 140 workspace image

`Dockerfile` builds `quay.io/rhoai3-coding-demo/rhoai3-ws-140` on Red Hat Dev Spaces UDI 3.29.1, which already
carries JDK 11/17/21, Maven 3.9.9, Git and Node 22. It adds what the MTA 8.3 documentation installs for a Java
analysis: MTA Core and the MTA Java language extension (not the extension pack), the Language Support for Java
extension, and the MTA analyzer RPC binary at `/opt/mta-analyzer-rpc/mta-analyzer-rpc`, which the workspace
settings name as `mta-core.analyzerPath`. It also installs GNU Stow 2.4.1, which Dev Spaces needs for persisted user
homes. `artifacts.lock.json` pins every download by sha256; the downloads stay outside Git.

| Script | When to run |
|---|---|
| `build.sh TAG [--push]` | When the lock file or Dockerfile changes. Downloads and verifies the analyzer archive and the three extensions, builds `rhoai3-ws-140:TAG` for linux/amd64 with Podman, checks the image from the inside (checksums, extension set, analyzer start, Java 21, Maven, Node, Stow) and, with `--push`, publishes it and prints the digest. Record that digest in `artifacts.lock.json` (`published_image`) and in `gitops/stages/070-advanced-app-platform/070-rhdh/templates/migrate-with-mta/skeleton/devfile.yaml`. The Quay repository is public, so workspaces pull it without a pull secret. Needs a running Podman machine (`STAGE140_PODMAN_CONNECTION`, default `podman-machine-default`). |
