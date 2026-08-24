# rhoai3 workspace overlays on Red Hat Dev Spaces UDI 3.28.2.
#
# Parent digest is the linux/amd64 udi-rhel9:3.28.2 image
# (RHSA-2026:25123 lists the same digest for Dev Spaces 3.28).
# There is no floating :3.28 tag in registry.redhat.io/devspaces/udi-rhel9.
#
# persistUserHome custom-image rules (Dev Spaces 3.28 Administration Guide
# ch.10): stow >= 2.4.0, HOME=/home/user, user-home content in /home/tooling.
# The UDI 3.28.2 image ships stow 2.3.2; foundation installs GNU Stow 2.4.1
# from ftp.gnu.org (not EPEL/COPR).
#
# Pattern (shape only): che-incubator/cli-ai-tools Dockerfile — FROM UDI,
# USER 0, pin CLIs into /usr/local, USER 10001, pre-create config dirs.
# Do not consume that image or its destfile.
#
# Targets: rhoai3-udi-foundation, rhoai3-ws-060, rhoai3-ws-070, rhoai3-ws-080

ARG UDI_IMAGE="registry.redhat.io/devspaces/udi-rhel9:3.28.2@sha256:80c9c0c3aa02ae7b447c33a8bb9aff07fc243b2b484db28975b79b9007612629"

FROM ${UDI_IMAGE} AS udi

# ---------------------------------------------------------------------------
# Foundation: CA/trust env, empty config dirs, uv, stow 2.4.1
# ---------------------------------------------------------------------------
FROM udi AS rhoai3-udi-foundation
ARG STOW_VERSION=2.4.1
ARG UV_VERSION=0.8.15
USER 0
ENV HOME=/home/user \
    NODE_USE_SYSTEM_CA=1 \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk \
    JAVA_HOME_21=/usr/lib/jvm/java-21-openjdk
# UDI 3.28.2 already ships perl, make, tar, gzip, git, unzip (inspected).
# Skip dnf: the image is not subscribed, and gcc is not required for GNU Stow.
RUN curl -fsSL "https://ftp.gnu.org/gnu/stow/stow-${STOW_VERSION}.tar.gz" -o /tmp/stow.tar.gz \
    && mkdir -p /tmp/stow-src \
    && tar -xzf /tmp/stow.tar.gz -C /tmp/stow-src --strip-components=1 \
    && cd /tmp/stow-src && ./configure --prefix=/usr && make && make install \
    && rm -rf /tmp/stow.tar.gz /tmp/stow-src \
    && stow --version | grep -q "2.4" \
    && curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" -o /tmp/uv.tar.gz \
    && tar -xzf /tmp/uv.tar.gz -C /tmp \
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
RUN mkdir -p /opt/rhoai3/extensions \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /opt/rhoai3/extensions/kilo-code.vsix \
         "https://open-vsx.org/api/kilocode/kilo-code/linux-x64/${KILO_VERSION}/file/kilocode.kilo-code-${KILO_VERSION}@linux-x64.vsix" \
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
RUN mkdir -p /usr/local/lib/opencode /opt/rhoai3 \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /tmp/opencode.tgz \
         "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
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
ARG HERMES_VERSION=0.20.5
ARG HERMES_DATE=2026.8.19
ARG MTA_VSIX_VERSION=8.2.0
ARG REDHAT_JAVA_VERSION=1.47.0
ARG KANTRA_VERSION=v0.10.0-beta.1
COPY scripts/assert-hermes-source-pin.py /opt/rhoai3/assert-hermes-source-pin.py
USER 0
ENV HERMES_HOME=/projects/modernized/.hermes/home \
    HERMES_MANAGED_DIR=/projects/.platform/hermes \
    HERMES_WEB_DIST=/usr/local/share/hermes/web_dist
RUN mkdir -p /opt/rhoai3/extensions /opt/hermes-agent /usr/local/share/hermes/web_dist \
         /opt/kantra /home/tooling/.hermes \
    && git clone --depth 1 --branch "${HERMES_GIT_REF}" \
         https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent \
    && python3 /opt/rhoai3/assert-hermes-source-pin.py \
         --agent-src /opt/hermes-agent \
         --version "${HERMES_VERSION}" \
         --date "${HERMES_DATE}" \
    && python3 -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --upgrade pip \
    && /opt/hermes-venv/bin/pip install -e "/opt/hermes-agent" \
    && ln -sf /opt/hermes-venv/bin/hermes /usr/local/bin/hermes \
    && if [ -d /opt/hermes-agent/hermes_cli/web_dist ]; then \
         cp -a /opt/hermes-agent/hermes_cli/web_dist/. /usr/local/share/hermes/web_dist/; \
       elif [ -d /opt/hermes-agent/web_dist ]; then \
         cp -a /opt/hermes-agent/web_dist/. /usr/local/share/hermes/web_dist/; \
       else \
         echo "WARN: no prebuilt web_dist in Hermes ${HERMES_GIT_REF}; HERMES_WEB_DIST dir is empty until dest install-web-dist"; \
       fi \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /opt/rhoai3/extensions/mta.vsix \
         "https://open-vsx.org/api/redhat/mta-vscode-extension/${MTA_VSIX_VERSION}/file/redhat.mta-vscode-extension-${MTA_VSIX_VERSION}.vsix" \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /opt/rhoai3/extensions/mta-core.vsix \
         "https://open-vsx.org/api/redhat/mta-core/${MTA_VSIX_VERSION}/file/redhat.mta-core-${MTA_VSIX_VERSION}.vsix" \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /opt/rhoai3/extensions/redhat-java.vsix \
         "https://open-vsx.org/api/redhat/java/${REDHAT_JAVA_VERSION}/file/redhat.java-${REDHAT_JAVA_VERSION}.vsix" \
    && curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 300 \
         -o /opt/rhoai3/extensions/mta-java.vsix \
         "https://open-vsx.org/api/redhat/mta-java/${MTA_VSIX_VERSION}/file/redhat.mta-java-${MTA_VSIX_VERSION}.vsix" \
    && test -s /opt/rhoai3/extensions/mta.vsix \
    && test -s /opt/rhoai3/extensions/mta-core.vsix \
    && test -s /opt/rhoai3/extensions/redhat-java.vsix \
    && test -s /opt/rhoai3/extensions/mta-java.vsix \
    && curl -fsSL --retry 3 --max-time 1200 \
         -o /tmp/kantra.zip \
         "https://github.com/konveyor/kantra/releases/download/${KANTRA_VERSION}/kantra.linux.amd64.zip" \
    && python3 -m zipfile -e /tmp/kantra.zip /opt/kantra \
    && rm -f /tmp/kantra.zip \
    && chmod +x /opt/kantra/kantra \
    && ln -sf /opt/kantra/kantra /usr/local/bin/kantra \
    && ln -sf /opt/kantra/kantra /usr/local/bin/mta-cli \
    && printf '%s\n' \
         "# REFUSE - wrong SOUL.md" \
         "" \
         "This path is NOT the migration workspace identity." \
         "Set HERMES_HOME=/projects/modernized/.hermes/home" \
         > /home/tooling/.hermes/SOUL.md \
    && mkdir -p /etc/hermes \
    && printf 'unreleased\n' > /etc/hermes/IMAGE_DIGEST \
    && chown -R 10001:0 /opt/rhoai3 /opt/hermes-agent /opt/hermes-venv /opt/kantra \
         /usr/local/share/hermes /home/tooling/.hermes /etc/hermes
ENV DEFAULT_EXTENSIONS="/opt/rhoai3/extensions/mta.vsix;/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/redhat-java.vsix;/opt/rhoai3/extensions/mta-java.vsix"
USER 10001

# Stamp layer: CI rebuilds this target with --build-arg IMAGE_DIGEST=<oci digest
# of rhoai3-ws-080-unsigned>. The file records the unsigned image digest; the
# stamped image digest is different by construction (extra layer).
FROM rhoai3-ws-080-unsigned AS rhoai3-ws-080
ARG IMAGE_DIGEST=unreleased
USER 0
RUN mkdir -p /etc/hermes && printf '%s\n' "${IMAGE_DIGEST}" > /etc/hermes/IMAGE_DIGEST \
    && chown 10001:0 /etc/hermes/IMAGE_DIGEST
USER 10001
