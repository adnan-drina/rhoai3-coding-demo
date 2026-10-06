FROM registry.access.redhat.com/ubi9/ubi@sha256:dec374e05cc13ebbc0975c9f521f3db6942d27f8ccdf06b180160490eef8bdbc
# The binary build context is verified against release-source.json before upload.
RUN dnf install -y git-core libstdc++ findutils tar gzip && dnf clean all
COPY opencode /usr/local/bin/opencode
RUN chmod 0755 /usr/local/bin/opencode && /usr/local/bin/opencode --version | grep -Fx 1.18.16 \
    && mkdir -p /workspace /state && chgrp -R 0 /workspace /state && chmod -R g=u /workspace /state
# Mounted state/workspace volumes must be made writable by the admitted namespace fsGroup.
# Image group0 permissions alone do not qualify a nonzero namespace GID.
ENV TMPDIR=/tmp HOME=/state XDG_DATA_HOME=/state/data XDG_CONFIG_HOME=/state/config XDG_CACHE_HOME=/state/cache XDG_STATE_HOME=/state/state
USER 1001:0
WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]
