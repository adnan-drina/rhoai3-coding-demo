# Shared workspace image

`Dockerfile` extends the immutable published Hermes parent and replaces only the MTA CLI and editor extensions.
`artifacts.lock.json` pins the official MTA CLI Linux amd64 archive and binary and the four VSIX packages; the
downloads stay outside Git. `verify-image.py` runs inside the built image (Python is the image's own check runtime): it
checks the MTA and VSIX hashes, the Java external provider and analyzer bundle, `mta-cli version`, Java 21, Node and
the preserved Hermes runtime pin.

| Script | When to run |
|---|---|
| `build.sh MTA_ZIP TAG [--push]` | When the lock file or Dockerfile changes. Verifies the downloaded MTA ZIP and the extensions against the lock file, builds `quay.io/rhoai3-coding-demo/rhoai3-ws-080:TAG` for linux/amd64 with Podman, runs `verify-image.py` in it and, with `--push`, publishes it and prints the digest. Review the registry read-back and the pin changes before deploying. Needs a running Podman machine (`STAGE070_PODMAN_CONNECTION`, default `podman-machine-default`). |
