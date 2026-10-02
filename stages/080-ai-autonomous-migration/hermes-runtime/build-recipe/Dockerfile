# syntax=docker/dockerfile:1
# rhoai3 workspace overlays on Red Hat Dev Spaces UDI 3.29.1.
#
# Parent digest is the linux/amd64 udi-rhel9:3.29.1 image, measured
# 2026-08-24 via `podman manifest inspect` (same amd64 digest as tags
# 3.29 and 3.29-1784927049; older 3.29-1782991491 differs). Matching
# live CheCluster cheVersion 3.29.1. Do not treat overlay 3.28.2 as
# CheCluster-aligned.
#
# persistUserHome custom-image rules (Dev Spaces Administration Guide
# custom images / persistUserHome): stow >= 2.4.0, HOME=/home/user,
# user-home content in /home/tooling. The UDI 3.29.1 image ships stow
# 2.3.2; foundation installs GNU Stow 2.4.1 from ftp.gnu.org
# (not EPEL/COPR).
#
# Pattern (shape only): che-incubator/cli-ai-tools Dockerfile — FROM UDI,
# USER 0, pin CLIs into /usr/local, USER 10001, pre-create config dirs.
# Do not consume that image or its destfile.
#
# Remote ADD checksums measured 2026-08-25 (sha256 of the downloaded bytes).
# Hermes clone SHA is Operator 195540Zop (tag v2026.8.19). Do not invent SHAs.
#
# Targets: rhoai3-udi-foundation, rhoai3-ws-060, rhoai3-ws-070, rhoai3-ws-080

ARG UDI_IMAGE="registry.redhat.io/devspaces/udi-rhel9:3.29.1@sha256:420f18fc64f0d05ccdabafdde946eb1fdff0f1c7e14e1dc4a43fdfb917267bed"

FROM ${UDI_IMAGE} AS udi

# ---------------------------------------------------------------------------
# Foundation: CA/trust env, empty config dirs, uv, stow 2.4.1
# ---------------------------------------------------------------------------
FROM udi AS rhoai3-udi-foundation
ARG STOW_VERSION=2.4.1
ARG UV_VERSION=0.8.15
USER 0
LABEL demo.rhoai.io/overlay="rhoai3-udi-foundation"
ENV HOME=/home/user \
    NODE_USE_SYSTEM_CA=1 \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk \
    JAVA_HOME_21=/usr/lib/jvm/java-21-openjdk
# UDI 3.29.1 already ships perl, make, tar, gzip, git, unzip (inspected).
# Stow is still 2.3.2; foundation installs 2.4.1.
# Skip dnf: the image is not subscribed, and gcc is not required for GNU Stow.
ADD --checksum=sha256:2a671e75fc207303bfe86a9a7223169c7669df0a8108ebdf1a7fe8cd2b88780b \
    https://ftp.gnu.org/gnu/stow/stow-2.4.1.tar.gz /tmp/stow.tar.gz
ADD --checksum=sha256:be9878e9d08ebcb621a683aba52e7fb8bbf92b2532e0d759026ffcc067673042 \
    https://github.com/astral-sh/uv/releases/download/0.8.15/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz
RUN mkdir -p /tmp/stow-src
WORKDIR /tmp/stow-src
RUN tar -xzf /tmp/stow.tar.gz --strip-components=1 \
    && ./configure --prefix=/usr && make && make install \
    && rm -rf /tmp/stow.tar.gz /tmp/stow-src \
    && stow --version | grep -q "2.4"
WORKDIR /
RUN tar -xzf /tmp/uv.tar.gz -C /tmp \
    && install -m 0755 /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv \
    && install -m 0755 /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/uvx \
    && rm -rf /tmp/uv.tar.gz /tmp/uv-x86_64-unknown-linux-gnu \
    && mkdir -p \
         /home/tooling/.config/kilo \
         /home/tooling/.config/opencode \
         /home/user/.config/kilo \
         /home/user/.config/opencode \
    && chown -R 10001:0 /home/tooling/.config /home/user/.config \
    && printf '%s\n' "rhoai3-udi-foundation" > /etc/rhoai3-workspace-overlay \
    && stow --version
USER 10001

# ---------------------------------------------------------------------------
# 060: Kilo VSIX baked; DEFAULT_EXTENSIONS points at the baked path
# ---------------------------------------------------------------------------
FROM rhoai3-udi-foundation AS rhoai3-ws-060
ARG KILO_VERSION=7.4.8
USER 0
LABEL demo.rhoai.io/overlay="rhoai3-ws-060"
ADD --checksum=sha256:dabc0e79b98a80b946c222c968e367a71776273ce774a07a722687d3114b6a4f \
    https://open-vsx.org/api/kilocode/kilo-code/linux-x64/7.4.8/file/kilocode.kilo-code-7.4.8@linux-x64.vsix \
    /opt/rhoai3/extensions/kilo-code.vsix
RUN mkdir -p /opt/rhoai3/extensions \
    && test -s /opt/rhoai3/extensions/kilo-code.vsix \
    && chown -R 10001:0 /opt/rhoai3
ENV DEFAULT_EXTENSIONS=/opt/rhoai3/extensions/kilo-code.vsix
USER 10001

# ---------------------------------------------------------------------------
# 070: OpenCode CLI + spec-kit CLI, version-pinned
# ---------------------------------------------------------------------------
FROM rhoai3-udi-foundation AS rhoai3-ws-070
ARG OPENCODE_VERSION=1.18.16
ARG SPECIFY_CLI_VERSION=0.16.1
USER 0
LABEL demo.rhoai.io/overlay="rhoai3-ws-070"
ADD --checksum=sha256:286e07355df06738c1905955be15b7fbc10a7b12d931de9394a6f7597246750b \
    https://github.com/anomalyco/opencode/releases/download/v1.18.16/opencode-linux-x64.tar.gz \
    /tmp/opencode.tgz
RUN mkdir -p /usr/local/lib/opencode /opt/rhoai3 \
    && tar -xzf /tmp/opencode.tgz -C /usr/local/lib/opencode \
    && OC_BIN="$(find /usr/local/lib/opencode -type f -name opencode | head -n 1)" \
    && test -n "${OC_BIN}" && chmod +x "${OC_BIN}" \
    && ln -sf "${OC_BIN}" /usr/local/bin/opencode \
    && rm -f /tmp/opencode.tgz \
    && test -x /usr/local/bin/opencode \
    && /home/tooling/.venv/bin/pip install --prefix /usr/local \
         "specify-cli==${SPECIFY_CLI_VERSION}" \
    && python3 -c "import shutil,sys; sys.exit(0 if shutil.which('specify') or shutil.which('specify-cli') else 1)" \
    && printf '%s\n' "opencode=${OPENCODE_VERSION}" "specify-cli=${SPECIFY_CLI_VERSION}" > /opt/rhoai3/070.pins \
    && chown -R 10001:0 /opt/rhoai3 /home/tooling/.config/opencode /home/user/.config/opencode
USER 10001

# ---------------------------------------------------------------------------
# 080: Hermes 0.20.5 + dashboard dist + MTA VSIX + kantra
# ---------------------------------------------------------------------------
FROM rhoai3-udi-foundation AS rhoai3-ws-080-unsigned
ARG HERMES_GIT_REF=v2026.8.19
ARG HERMES_GIT_SHA=fcbd1076a93841fa88855acce810e342a5b78101
ARG HERMES_VERSION=0.20.5
ARG HERMES_DATE=2026.8.19
# B11 runtime patch series (stages/080-ai-autonomous-migration/hermes-runtime):
# identical successful tool-call streak halt + halt propagation, terminal
# transport-metadata identity, stub retrievability, kanban halt accounting,
# incomplete-output and persistent-429 named stops (0005, 0006), per-run
# request pacer (0007; active only when RHOAI3_REQUEST_BUDGET/_LEDGER are set),
# explicit auxiliary per-call values over task extra_body (0008), neutral
# local-budget deferral (0009), reserved-and-settled token accounting (0010),
# worker stop request as one native block and read-only log context search
# family halt (0011), read-only cycle and identical pre-execution refusal
# halts (0012), review handoff terminal in the stop guard (0013), near-duplicate
# loop halt (0014), any new line is progress in that guard (0015), the --skills
# preload records what it actually loaded (0016), loop escalation to a
# thinking request profile after the third identical-call note (0017), its
# same-result / same-call / repeat-read triggers, restart bound and typed-repair
# end (0018), and a terminal
# call cut at the foreground limit saying so (0019), read_file reporting a line
# cut at the per-line cap (0020).
# Staged into the build context by the operator (cp .../patches/*.patch
# out/hermes-runtime-patches/). The git tree of the patched source must equal
# HERMES_PATCHED_TREE or the build fails.
ARG HERMES_PATCHED_TREE=8328461c4d05e0760e694ea5b9970b019366421a
ARG MTA_VSIX_VERSION=8.2.0
ARG REDHAT_JAVA_VERSION=1.47.0
ARG KANTRA_VERSION=v0.10.0-beta.1
# MTA CLI 8.2 (the pinned, admissible analyzer: .hermes/pins.json mta_cli).
# The archive comes from the MTA download page (Red Hat login), so it is
# COPY'd from out/, never fetched here: "Migration Toolkit CLI — CLI for
# Linux x86_64" saved under its download name; the build refuses a file
# whose sha256 differs from the published checksum below.
ARG MTA_CLI_VERSION=8.2.1.1
ARG MTA_CLI_ZIP_SHA256=988db13d51a2fb34dbc9f50ac37d43c7e65fb7f0ed502f14ad140dbf681e6ecc
COPY out/mta-${MTA_CLI_VERSION}-cli-linux-amd64.zip /tmp/mta-cli.zip
RUN echo "${MTA_CLI_ZIP_SHA256}  /tmp/mta-cli.zip" | sha256sum -c -
COPY scripts/assert-hermes-source-pin.py /opt/rhoai3/assert-hermes-source-pin.py
COPY out/hermes-runtime-patches/ /opt/rhoai3/hermes-runtime-patches/
COPY scripts/assert-zip-exec-bits.py /opt/rhoai3/assert-zip-exec-bits.py
COPY scripts/normalize-exec-bits.py /opt/rhoai3/normalize-exec-bits.py
USER 0
LABEL demo.rhoai.io/overlay="rhoai3-ws-080"
# /usr/bin/python3 is 3.9 on UDI 3.29.1; Hermes v2026.8.19 isolate-build
# wants setuptools==83 (Requires-Python >=3.10). Use UDI-shipped
# /usr/bin/python3.11. Do not use /home/tooling/.venv (persistUserHome
# stows that tree; a symlink out of it dangles at runtime).
# Dashboard: Research 181247ZS extra [web] (not [messaging], not skip
# because core already declares fastapi). Do not NodeSource 20. Do not
# Playwright. Do not run tsc/vite under `podman build --arch amd64` on
# Apple Silicon: qemu segfaults (signal 11, exit 139; 2026-08-24). JS
# assets are arch-independent — scripts/bake-web-dist-host.sh builds
# pin v2026.8.19 with Node 22.23.1 (UDI version) and COPY below.
ENV HERMES_HOME=/projects/modernized/.hermes/home \
    HERMES_MANAGED_DIR=/projects/.platform/hermes \
    HERMES_WEB_DIST=/usr/local/share/hermes/web_dist
ADD --checksum=sha256:1f9c50dda0d2ecdbc46a98139b99542fa1d2a3d37bb1025c11d4b9688f9f6a00 \
    https://open-vsx.org/api/redhat/mta-vscode-extension/8.2.0/file/redhat.mta-vscode-extension-8.2.0.vsix \
    /opt/rhoai3/extensions/mta.vsix
ADD --checksum=sha256:00f52c7613296e4d7b9461b06818b8baac4c92869335e1f2558dad4e32c5ed75 \
    https://open-vsx.org/api/redhat/mta-core/8.2.0/file/redhat.mta-core-8.2.0.vsix \
    /opt/rhoai3/extensions/mta-core.vsix
ADD --checksum=sha256:cf184d6495a2e268c43731ec3bbe058ceaf3b65e6e65b554dda30f3b90f0191a \
    https://open-vsx.org/api/redhat/java/1.47.0/file/redhat.java-1.47.0.vsix \
    /opt/rhoai3/extensions/redhat-java.vsix
ADD --checksum=sha256:609a782da8d575d7cade35bdb6eb04a0e36e3d2f68c0536d07fba048310487aa \
    https://open-vsx.org/api/redhat/mta-java/8.2.0/file/redhat.mta-java-8.2.0.vsix \
    /opt/rhoai3/extensions/mta-java.vsix
ADD --checksum=sha256:f2ef902d4de32a27839753417814454257d91d76dada1a4ad96a1feb698b863d \
    https://github.com/konveyor/kantra/releases/download/v0.10.0-beta.1/kantra.linux.amd64.zip \
    /tmp/kantra.zip
RUN mkdir -p /opt/rhoai3/extensions /opt/hermes-agent /usr/local/share/hermes/web_dist \
         /opt/kantra /opt/mta-cli /home/tooling/.hermes \
    && git clone --depth 1 --branch "${HERMES_GIT_REF}" \
         https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent \
    && test "$(git -C /opt/hermes-agent rev-parse HEAD)" = "${HERMES_GIT_SHA}" \
    && python3 /opt/rhoai3/assert-hermes-source-pin.py \
         --agent-src /opt/hermes-agent \
         --version "${HERMES_VERSION}" \
         --date "${HERMES_DATE}" \
    && test "$(ls /opt/rhoai3/hermes-runtime-patches/*.patch | wc -l)" -eq 20 \
    && for p in /opt/rhoai3/hermes-runtime-patches/*.patch; do \
         git -C /opt/hermes-agent apply --index "$p" || exit 1; \
       done \
    && test "$(git -C /opt/hermes-agent write-tree)" = "${HERMES_PATCHED_TREE}" \
    && (cd /opt/rhoai3/hermes-runtime-patches && sha256sum *.patch) \
         > /opt/rhoai3/hermes-runtime-patches.sha256 \
    && /usr/bin/python3.11 -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --upgrade pip \
    && /opt/hermes-venv/bin/pip install -e "/opt/hermes-agent[web]" \
    && ln -sf /opt/hermes-venv/bin/hermes /usr/local/bin/hermes
# Host-baked web_dist (see bake-web-dist-host.sh). Fail closed if empty.
COPY out/web_dist/ /usr/local/share/hermes/web_dist/
RUN test -s /usr/local/share/hermes/web_dist/index.html
# kantra is extracted with unzip, not `python3 -m zipfile -e`: the latter
# discards Unix modes, so the whole tree lands 644 and analysis dies at
# java-external-provider. /opt/kantra is chown 10001 below and the workspace
# runs as a different uid, so a lost exec bit cannot be repaired at workspace
# start - it has to be right in the image. assert-zip-exec-bits.py checks the
# invariant (every entry the archive marks executable is executable on disk)
# rather than a list of names, so a future KANTRA_VERSION layout is covered.
RUN test -s /opt/rhoai3/extensions/mta.vsix \
    && test -s /opt/rhoai3/extensions/mta-core.vsix \
    && test -s /opt/rhoai3/extensions/redhat-java.vsix \
    && test -s /opt/rhoai3/extensions/mta-java.vsix \
    && unzip -q /tmp/kantra.zip -d /opt/kantra \
    && python3 /opt/rhoai3/assert-zip-exec-bits.py \
         --zip /tmp/kantra.zip --dest /opt/kantra \
    && rm -f /tmp/kantra.zip \
    && chmod +x /opt/kantra/kantra \
    && ln -sf /opt/kantra/kantra /usr/local/bin/kantra \
    # MTA CLI 8.2 at /opt/mta-cli (MTA_CLI_HOME default of scan-with-mta).
    # /usr/local/bin/mta-cli is the product binary, no longer a kantra alias:
    # the admission receipt rejects an alias (provenance kantra-fallback).
    && unzip -q /tmp/mta-cli.zip -d /opt/mta-cli \
    && python3 /opt/rhoai3/assert-zip-exec-bits.py \
         --zip /tmp/mta-cli.zip --dest /opt/mta-cli \
    && rm -f /tmp/mta-cli.zip \
    && test -x /opt/mta-cli/mta-cli \
    # dest-init's kantra-assert-exec treats every ELF or shebang file under the
    # install prefix as runnable and refuses the tree when one lacks the exec
    # bit and the (random OpenShift) uid cannot chmod it. The 8.2.1.1 archive
    # ships rulesets/go/fips/tests/data/build/build.sh 0644 (measured live
    # 2026-09-09: the scan fell through to kantra). Normalize at build time,
    # as root, with the checker's own definition of runnable.
    && python3 /opt/rhoai3/normalize-exec-bits.py /opt/mta-cli /opt/kantra \
    && ln -sf /opt/mta-cli/mta-cli /usr/local/bin/mta-cli \
    && printf '%s\n' "mta-cli=${MTA_CLI_VERSION}" "mta-cli.sha256=$(sha256sum /opt/mta-cli/mta-cli | cut -d' ' -f1)" \
         "kantra=${KANTRA_VERSION}" "hermes=${HERMES_VERSION}" \
         "hermes.source_sha=${HERMES_GIT_SHA}" "hermes.patched_tree=${HERMES_PATCHED_TREE}" \
         > /opt/rhoai3/080.pins \
    && printf '%s\n' \
         "# REFUSE - wrong SOUL.md" \
         "" \
         "This path is NOT the migration workspace identity." \
         "Set HERMES_HOME=/projects/modernized/.hermes/home" \
         > /home/tooling/.hermes/SOUL.md \
    && mkdir -p /etc/hermes \
    && printf 'unreleased\n' > /etc/hermes/IMAGE_DIGEST \
    && chown -R 10001:0 /opt/rhoai3 /opt/hermes-agent /opt/hermes-venv /opt/kantra /opt/mta-cli \
         /usr/local/share/hermes /home/tooling/.hermes /etc/hermes
# Outcome-board authority code identity (planner.outcome_authority.code_identity
# over the staged tree); the build refuses a tree that does not compute it.
ARG OUTCOME_AUTHORITY_CODE_SHA256
COPY out/outcome-authority/ /opt/rhoai3/outcome-authority/
# The outcome-board authority (OUTCOME-BOARD-CONTRACT.md 3/8a): root-owned and
# not writable by any workspace uid or gid 0 -- AFTER the chown above, which
# would otherwise hand it to 10001:0. Its code identity is verified and stamped.
RUN test -n "${OUTCOME_AUTHORITY_CODE_SHA256}" \
    && chown -R 0:0 /opt/rhoai3/outcome-authority \
    && find /opt/rhoai3/outcome-authority -type d -exec chmod 0755 {} + \
    && find /opt/rhoai3/outcome-authority -type f -perm -u+x -exec chmod 0755 {} + \
    && find /opt/rhoai3/outcome-authority -type f ! -perm -u+x -exec chmod 0644 {} + \
    && ! find /opt/rhoai3/outcome-authority -name __pycache__ | grep -q . \
    && ident="$(cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 /opt/rhoai3/outcome-authority/kernel/outcome_authority.py code-identity --base /opt/rhoai3/outcome-authority)" \
    && test "${ident}" = "${OUTCOME_AUTHORITY_CODE_SHA256}" \
    && printf 'outcome_authority.code_sha256=%s\n' "${ident}" >> /opt/rhoai3/080.pins \
    && chmod 0644 /opt/rhoai3/080.pins
# Typed repair executor (V26-1; golden .hermes/pins.json typed_repair): harness
# tooling built by build-080-runtime-image.sh step 2b from the pinned sources
# (OpenRewrite 8.89.0, Apache-2.0; notices inside the jar), never a dependency
# of the migrated application. Checksum-gated, root-owned and read-only; the
# loop refuses any other jar by digest (_typed_repair.executor).
ARG TYPED_REPAIR_JAR_SHA256=768ba69f22b77de314b62cadaeee8620862f0616f2bf8f4ce284d58a9368a765
COPY out/typed-repair/typed-repair.jar /opt/rhoai3/typed-repair/typed-repair.jar
RUN echo "${TYPED_REPAIR_JAR_SHA256}  /opt/rhoai3/typed-repair/typed-repair.jar" | sha256sum -c - \
    && chown -R 0:0 /opt/rhoai3/typed-repair \
    && chmod 0755 /opt/rhoai3/typed-repair \
    && chmod 0644 /opt/rhoai3/typed-repair/typed-repair.jar \
    && printf 'typed_repair.jar_sha256=%s\n' "${TYPED_REPAIR_JAR_SHA256}" >> /opt/rhoai3/080.pins
ENV MTA_CLI_HOME=/opt/mta-cli
ENV DEFAULT_EXTENSIONS="/opt/rhoai3/extensions/mta.vsix;/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/redhat-java.vsix;/opt/rhoai3/extensions/mta-java.vsix"
USER 10001

# Stamp layer overwrites the unsigned target's literal `unreleased` so
# dest-init presence fail-close can pass (Architect 183448ZA). Do not
# compare this file to the destfile/registry manifest digest.
FROM rhoai3-ws-080-unsigned AS rhoai3-ws-080
ARG IMAGE_DIGEST=unreleased
USER 0
LABEL demo.rhoai.io/overlay="rhoai3-ws-080"
RUN mkdir -p /etc/hermes && printf '%s\n' "${IMAGE_DIGEST}" > /etc/hermes/IMAGE_DIGEST \
    && chown 10001:0 /etc/hermes/IMAGE_DIGEST
USER 10001
