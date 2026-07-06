# Validation Checklist

Use this checklist when reviewing README architecture text, namespace topology,
or GitOps scaffolding against the RHOAI architecture chapter.

## Documentation Review

- README architecture text identifies service-layer capabilities accurately.
- README architecture text identifies the RHOAI Operator as the management-layer
  meta-operator.
- Custom demo services are not described as native OpenShift AI services.
- RAG is described as using the integrated Llama Stack Operator only when that
  component is implemented or explicitly planned.
- Any platform support claim beyond the chapter is backed by
  `docs/PLATFORM_BASELINE.md` or official supported-configuration docs.

## Namespace Review

- Product operator namespace is `redhat-ods-operator` when predefined projects
  are used.
- Product application namespace is `redhat-ods-applications` when predefined
  projects are used.
- Default basic workbench namespace is `rhods-notebooks` when predefined
  projects are used.
- Demo workload namespaces are separate from OpenShift AI product namespaces.
- ISV or custom demo applications are not installed in OpenShift AI product
  namespaces.
- Custom project use is documented when the default namespaces are not used.

## Readonly Cluster Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get ns redhat-ods-operator redhat-ods-applications rhods-notebooks
oc get csv -n redhat-ods-operator
oc get pods -n redhat-ods-applications
```

Optional checks for custom namespace deployments:

```bash
oc get ns | rg "rhoai|demo|acme|maas"
oc get pods -A | rg "redhat-ods|rhods-notebooks|rhoai|demo|acme|maas"
```

## Fail Conditions

- GitOps installs demo applications in `redhat-ods-operator`,
  `redhat-ods-applications`, or `rhods-notebooks` without an official reason.
- README claims a component is native RHOAI when it is custom demo glue.
- README or manifests infer CR fields from this architecture chapter alone.
- Product namespace names are changed without documenting custom-project
  installation posture.
