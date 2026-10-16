# Platform tools image

`Dockerfile` builds the shared Git, Python and `oc` tooling image: the `oc` client comes from the pinned OpenShift
release image, Git and Python from UBI. Project application images are built by Tekton, not here.

| Script | When to run |
|---|---|
| `build.sh TAG [--push]` | When the Dockerfile pins change. Builds `quay.io/rhoai3-coding-demo/rhoai3-ws-080:platform-tools-TAG` for linux/amd64 with Podman, checks `git`, `python3` and `oc` run inside it and, with `--push`, publishes it and prints the digest. Needs a running Podman machine (`STAGE070_PODMAN_CONNECTION`); `REGISTRY_AUTH_FILE` is passed to build and push when set. |
