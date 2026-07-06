# Workbench CRD Patterns

These examples are minimal patterns for GitOps review. Verify active CRDs with
`oc explain` before promotion.

## Dashboard-Visible Custom ImageStream

```yaml
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: custom-workbench
  namespace: redhat-ods-applications
  annotations:
    opendatahub.io/notebook-image-name: Custom Workbench
    opendatahub.io/notebook-image-desc: Custom workbench image for the demo
  labels:
    app.kubernetes.io/created-by: byon
    app.kubernetes.io/part-of: workbenches
    opendatahub.io/component: "true"
    opendatahub.io/dashboard: "true"
    opendatahub.io/notebook-image: "true"
    platform.opendatahub.io/part-of: workbenches
spec:
  lookupPolicy:
    local: true
  tags:
    - name: "1.0"
      annotations:
        opendatahub.io/notebook-python-dependencies: '[{"name":"example","version":"1.0"}]'
        opendatahub.io/notebook-software: '[{"name":"Python","version":"v3.11"}]'
        opendatahub.io/workbench-image-recommended: "true"
        opendatahub.io/image-tag-outdated: "false"
      from:
        kind: DockerImage
        name: registry.example.com/team/custom-workbench@sha256:<digest>
      importPolicy:
        importMode: Legacy
      referencePolicy:
        type: Source
```

## Minimal Notebook Workbench Shape

```yaml
apiVersion: kubeflow.org/v1
kind: Notebook
metadata:
  name: team-workbench
  namespace: team-project
  annotations:
    notebooks.opendatahub.io/inject-auth: "true"
    notebooks.opendatahub.io/last-image-selection: "custom-workbench:1.0"
    notebooks.opendatahub.io/last-image-version-git-commit-selection: "<image-build-commit>"
    opendatahub.io/connections: ""
    opendatahub.io/image-display-name: Custom Workbench
    openshift.io/display-name: Team Workbench
  labels:
    kueue.x-k8s.io/queue-name: private-model-serving
spec:
  template:
    spec:
      serviceAccountName: team-workbench
      enableServiceLinks: false
      containers:
        - name: team-workbench
          image: image-registry.openshift-image-registry.svc:5000/redhat-ods-applications/custom-workbench:1.0
          imagePullPolicy: Always
          workingDir: /opt/app-root/src
          ports:
            - containerPort: 8888
              name: notebook-port
              protocol: TCP
          env:
            - name: NOTEBOOK_ARGS
              value: |-
                --ServerApp.port=8888
                --ServerApp.token=''
                --ServerApp.password=''
                --ServerApp.base_url=/notebook/team-project/team-workbench
                --ServerApp.quit_button=False
                --ServerApp.tornado_settings={"user":"<user>","hub_host":"https://<dashboard>", "hub_prefix":"/projects/team-project"}
            - name: JUPYTER_IMAGE
              value: image-registry.openshift-image-registry.svc:5000/redhat-ods-applications/custom-workbench:1.0
            - name: REQUESTS_CA_BUNDLE
              value: /etc/pki/tls/custom-certs/ca-bundle.crt
            - name: SSL_CERT_FILE
              value: /etc/pki/tls/custom-certs/ca-bundle.crt
          resources:
            requests:
              cpu: "1"
              memory: 8Gi
            limits:
              cpu: "2"
              memory: 8Gi
          volumeMounts:
            - mountPath: /opt/app-root/src
              name: team-workbench
            - mountPath: /dev/shm
              name: shm
      volumes:
        - name: team-workbench
          persistentVolumeClaim:
            claimName: team-workbench
        - name: shm
          emptyDir:
            medium: Memory
```

Notes:

- Remove `kueue.x-k8s.io/queue-name` unless the project has a matching
  `LocalQueue`.
- Add OAuth proxy, TLS, cookie secret, custom CA mount, and service account
  details using the official pattern and active CRD/schema verification.
- Keep dashboard-generated last-activity timestamps out of GitOps.
