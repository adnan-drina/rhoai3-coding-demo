# Preserve the published Hermes runtime; replace only the MTA product tools.
FROM quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:5aab5558481fcbb69483122543b7bcb96b9c34daf44466eea6d375fd37c92029
USER 0
RUN rm -rf /opt/mta-cli /opt/rhoai3/extensions
COPY mta-cli/ /opt/mta-cli/
COPY extensions/ /opt/rhoai3/extensions/
RUN echo "f2b01cdb4b6f73a8c19272eccd25893a47b1c02abb98438918afc06a219163bd  /opt/mta-cli/mta-cli" | sha256sum -c - \
    && python3 /opt/rhoai3/normalize-exec-bits.py /opt/mta-cli \
    && ln -sf /opt/mta-cli/mta-cli /usr/local/bin/mta-cli \
    && sed -i '/^mta-cli=/d; /^mta-cli.sha256=/d' /opt/rhoai3/080.pins \
    && printf '%s\n' 'mta-cli=8.3.0' 'mta-cli.sha256=f2b01cdb4b6f73a8c19272eccd25893a47b1c02abb98438918afc06a219163bd' >> /opt/rhoai3/080.pins \
    && grep -Fx 'hermes.patched_tree=9e5b79b9583d7aef515e8866eba993eb96679f4b' /opt/rhoai3/080.pins \
    && chown -R 10001:0 /opt/mta-cli /opt/rhoai3/extensions \
    && chmod -R g=u /opt/mta-cli /opt/rhoai3/extensions
ENV MTA_CLI_HOME=/opt/mta-cli
ENV DEFAULT_EXTENSIONS="/opt/rhoai3/extensions/mta-vscode-extension.vsix;/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/java.vsix;/opt/rhoai3/extensions/mta-java.vsix"
LABEL rhoai3.io.mta-cli.version="8.3.0" rhoai3.io.hermes.patched-tree="9e5b79b9583d7aef515e8866eba993eb96679f4b"
USER 10001
