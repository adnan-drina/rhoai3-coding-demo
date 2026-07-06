# Validation Checklist

Use this checklist before approving RHOAI install GitOps or running install
automation.

## Preflight

- Active baseline was checked in `docs/PLATFORM_BASELINE.md`.
- Exact OpenShift version was verified.
- OpenShift version is supported for the active RHOAI baseline.
- Cluster runs on the intended AWS/OpenShift environment.
- Current user has `cluster-admin`.
- Current user is not `kubeadmin`.
- Default storage class supports dynamic provisioning.
- Identity provider exists.
- Required Red Hat subscriptions are available.
- Open Data Hub is not installed.
- Required registry/subscription domains are reachable for a connected install.
- Required component dependencies are planned before components are set to
  `Managed`.

## GitOps Review

- Official CLI resource shapes are translated into GitOps manifests.
- ArgoCD Application applies the install manifests.
- Long-lived resources are not applied manually outside ArgoCD.
- Operator namespace is `redhat-ods-operator` unless a custom namespace is
  intentionally documented.
- Custom application namespace has
  `opendatahub.io/application-namespace: "true"`.
- Subscription uses verified package/channel/source values.
- `startingCSV` is omitted unless a pinned version is intentionally required.
- `DataScienceCluster/default-dsc` uses documented component names and
  `managementState` values.
- README, operations docs, manifests, and validation scripts agree.

## Readonly Cluster Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc version
oc whoami
oc auth can-i '*' '*' --all-namespaces
oc get storageclass
oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}{"\n"}'
oc get csv -A | rg -i "open data hub|opendatahub|odh"
oc get packagemanifest rhods-operator -n openshift-marketplace \
  -o jsonpath='{range .status.channels[*]}{.name}{"\n"}{end}'
```

Post-install checks:

```bash
oc get subscription rhods-operator -n redhat-ods-operator -o yaml
oc get csv -n redhat-ods-operator
oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}{"\n"}'
oc get datasciencecluster default-dsc -o jsonpath='{.status.installedComponents}{"\n"}'
oc get pods -n redhat-ods-applications
```

## Fail Conditions

- OpenShift version is unsupported or unverified.
- Installation uses `kubeadmin`.
- GitOps hard-codes an unverified channel or package source.
- Component is set `Managed` without required dependency planning.
- Custom namespace labels are missing.
- Open Data Hub is present.
- `DataScienceCluster` remains non-ready without a documented diagnostic path.
