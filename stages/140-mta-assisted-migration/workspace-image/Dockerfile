# Stage 140 workspace: Red Hat Dev Spaces UDI 3.29.1 plus the MTA 8.3.3 VS Code extensions and analyzer, as the
# MTA documentation installs them for one language: MTA Core with the Java language extension (not the Developer
# Preview extension pack), the Language Support for Java extension that mta-java depends on, and the analyzer RPC
# binary downloaded ahead of time ("Configuring and using the MTA analyzer RPC binary in your system"). build.sh puts
# only checksum-verified files from artifacts.lock.json into the build context.
# UDI 3.29.1 ships JDK 11/17/21, Maven 3.9.9, Git and Node 22, the Developer Lightspeed for MTA prerequisites.
FROM registry.redhat.io/devspaces/udi-rhel9:3.29.1@sha256:420f18fc64f0d05ccdabafdde946eb1fdff0f1c7e14e1dc4a43fdfb917267bed
USER 0
# The CheCluster persists user homes; the Dev Spaces custom-image rules require GNU Stow 2.4.0 or later, and UDI 3.29.1
# ships 2.3.2 (same checksummed source as the rhoai3-udi-foundation image).
ADD --checksum=sha256:2a671e75fc207303bfe86a9a7223169c7669df0a8108ebdf1a7fe8cd2b88780b \
    https://ftp.gnu.org/gnu/stow/stow-2.4.1.tar.gz /tmp/stow.tar.gz
RUN mkdir -p /tmp/stow-src && tar -xzf /tmp/stow.tar.gz -C /tmp/stow-src --strip-components=1 \
    && cd /tmp/stow-src && ./configure --prefix=/usr && make && make install \
    && cd / && rm -rf /tmp/stow.tar.gz /tmp/stow-src && stow --version | grep -q '2\.4'
COPY extensions/ /opt/rhoai3/extensions/
COPY mta-analyzer-rpc /opt/mta-analyzer-rpc/mta-analyzer-rpc
COPY artifacts.lock.json /opt/rhoai3/stage140-artifacts.lock.json
RUN chmod 0755 /opt/mta-analyzer-rpc/mta-analyzer-rpc \
    && chown -R 10001:0 /opt/rhoai3 /opt/mta-analyzer-rpc \
    && chmod -R g=u /opt/rhoai3 /opt/mta-analyzer-rpc
ENV JAVA_HOME_21=/usr/lib/jvm/java-21-openjdk \
    NODE_USE_SYSTEM_CA=1 \
    MTA_ANALYZER_RPC=/opt/mta-analyzer-rpc/mta-analyzer-rpc \
    DEFAULT_EXTENSIONS="/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/java.vsix;/opt/rhoai3/extensions/mta-java.vsix"
LABEL demo.rhoai.io/overlay="rhoai3-ws-140" rhoai3.io.mta.version="8.3.3"
USER 10001
