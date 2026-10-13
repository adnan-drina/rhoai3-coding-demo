# The CLI is extracted from the target OpenShift release; UBI supplies Git/Python.
FROM quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:3d64eeab58a903645291619362041d5e6c6ccbf45210f8a4fc1b8a818bc820bf AS cli
FROM registry.access.redhat.com/ubi9/python-39@sha256:4b49722c63ead686bb7da378813012ec6b60ecedf05d59ba8db7f0c9de7aa459
COPY --from=cli /usr/bin/oc /usr/local/bin/oc
USER 1001
ENTRYPOINT []
CMD ["/bin/bash"]
