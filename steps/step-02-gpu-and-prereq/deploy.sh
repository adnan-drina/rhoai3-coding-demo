#!/usr/bin/env bash
# Step 02: GPU Infrastructure & Prerequisites - Deploy Script
# Deploys operator prerequisites for RHOAI 3.4 + MaaS:
# - User Workload Monitoring
# - NFD Operator + Instance
# - GPU Operator + ClusterPolicy + DCGM Dashboard
# - OpenShift Serverless + KnativeServing
# - LeaderWorkerSet Operator
# - Red Hat Connectivity Link (RHCL)
# - GPU MachineSets (AWS)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-02-gpu-and-prereq"

load_env
check_oc_logged_in

log_step "Step 02: GPU Infrastructure & Prerequisites"

log_step "Checking prerequisites..."

if ! oc get applications -n openshift-gitops step-01-rhoai &>/dev/null; then
    log_error "step-01-rhoai Argo CD Application not found!"
    log_info "Please run: ./steps/step-01-rhoai/deploy.sh first"
    exit 1
fi
log_success "Prerequisites verified"

log_step "Creating Argo CD Application for GPU Infrastructure"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"

log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Waiting for NFD Operator..."
until oc get crd nodefeaturediscoveries.nfd.openshift.io &>/dev/null; do
    log_info "Waiting for NFD CRD..."
    sleep 10
done
log_success "NFD CRD available"

log_step "Waiting for GPU Operator..."
until oc get crd clusterpolicies.nvidia.com &>/dev/null; do
    log_info "Waiting for GPU Operator CRD..."
    sleep 10
done
log_success "GPU Operator CRD available"

log_step "Waiting for Serverless Operator..."
until oc get crd knativeservings.operator.knative.dev &>/dev/null; do
    log_info "Waiting for Knative CRD..."
    sleep 10
done
log_success "Serverless CRD available"

log_step "Waiting for LeaderWorkerSet Operator..."
until oc get csv -n openshift-lws-operator -o jsonpath='{.items[?(@.spec.displayName=="Red Hat build of Leader Worker Set")].status.phase}' 2>/dev/null | grep -q "Succeeded"; do
    log_info "Waiting for LWS Operator..."
    sleep 10
done
log_success "LeaderWorkerSet Operator ready"

log_step "Waiting for cert-manager Operator..."
until oc get crd certificates.cert-manager.io &>/dev/null; do
    log_info "Waiting for cert-manager CRD..."
    sleep 10
done
log_success "cert-manager CRD available"

log_step "Waiting for Red Hat Connectivity Link (RHCL)..."
until oc get crd authpolicies.kuadrant.io &>/dev/null; do
    log_info "Waiting for RHCL AuthPolicy CRD..."
    sleep 10
done
log_success "RHCL AuthPolicy CRD available"

log_step "Creating Kuadrant instance..."
ensure_namespace "kuadrant-system"

cat <<EOF | oc apply -f -
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: kuadrant-system
EOF

log_info "Waiting for Kuadrant to become ready..."
until oc wait Kuadrant -n kuadrant-system kuadrant --for=condition=Ready --timeout=10m 2>/dev/null; do
    sleep 10
done
log_success "Kuadrant ready"

log_step "Configuring Authorino with TLS..."
oc annotate svc/authorino-authorino-authorization \
    service.beta.openshift.io/serving-cert-secret-name=authorino-server-cert \
    -n kuadrant-system --overwrite 2>/dev/null || true
sleep 5

cat <<EOF | oc apply -f -
apiVersion: operator.authorino.kuadrant.io/v1beta1
kind: Authorino
metadata:
  name: authorino
  namespace: kuadrant-system
spec:
  replicas: 1
  clusterWide: true
  listener:
    tls:
      enabled: true
      certSecretRef:
        name: authorino-server-cert
  oidcServer:
    tls:
      enabled: false
EOF

until oc wait --for=condition=ready pod -l authorino-resource=authorino -n kuadrant-system --timeout=150s 2>/dev/null; do
    sleep 5
done
log_success "Authorino ready with TLS"

# Deploy MachineSets (cluster-specific, not in GitOps)
log_step "Deploying GPU MachineSets"

CLUSTER_ID=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
AMI_ID=$(oc get machineset -n openshift-machine-api -o jsonpath='{.items[0].spec.template.spec.providerSpec.value.ami.id}')
REGION=$(oc get infrastructure cluster -o jsonpath='{.status.platformStatus.aws.region}')
AZ=$(oc get machineset -n openshift-machine-api -o jsonpath='{.items[0].spec.template.spec.providerSpec.value.placement.availabilityZone}')

log_info "Cluster: $CLUSTER_ID | Region: $REGION | AZ: $AZ"

for instance_type in "g6e.2xlarge"; do
    ms_name="${CLUSTER_ID}-gpu-${instance_type//./-}-${AZ}"

    if oc get machineset -n openshift-machine-api "$ms_name" &>/dev/null; then
        log_info "MachineSet $ms_name already exists, skipping..."
        continue
    fi

    log_info "Creating MachineSet: $ms_name"

    cat <<EOF | oc apply -f -
apiVersion: machine.openshift.io/v1beta1
kind: MachineSet
metadata:
  name: ${ms_name}
  namespace: openshift-machine-api
  labels:
    machine.openshift.io/cluster-api-cluster: ${CLUSTER_ID}
  annotations:
    machine.openshift.io/GPU: "1"
    machine.openshift.io/memoryMb: "65536"
    machine.openshift.io/vCPU: "8"
spec:
  replicas: 2
  selector:
    matchLabels:
      machine.openshift.io/cluster-api-cluster: ${CLUSTER_ID}
      machine.openshift.io/cluster-api-machineset: ${ms_name}
  template:
    metadata:
      labels:
        machine.openshift.io/cluster-api-cluster: ${CLUSTER_ID}
        machine.openshift.io/cluster-api-machine-role: gpu-worker
        machine.openshift.io/cluster-api-machine-type: gpu-worker
        machine.openshift.io/cluster-api-machineset: ${ms_name}
    spec:
      lifecycleHooks: {}
      metadata:
        labels:
          node-role.kubernetes.io/gpu: ""
      taints:
        - key: nvidia.com/gpu
          value: "true"
          effect: NoSchedule
      providerSpec:
        value:
          apiVersion: machine.openshift.io/v1beta1
          kind: AWSMachineProviderConfig
          ami:
            id: ${AMI_ID}
          instanceType: ${instance_type}
          placement:
            availabilityZone: ${AZ}
            region: ${REGION}
          blockDevices:
            - ebs:
                encrypted: true
                volumeSize: 200
                volumeType: gp3
          credentialsSecret:
            name: aws-cloud-credentials
          iamInstanceProfile:
            id: ${CLUSTER_ID}-worker-profile
          securityGroups:
            - filters:
                - name: tag:Name
                  values:
                    - ${CLUSTER_ID}-node
            - filters:
                - name: tag:Name
                  values:
                    - ${CLUSTER_ID}-lb
          subnet:
            filters:
              - name: tag:Name
                values:
                  - ${CLUSTER_ID}-subnet-private-${AZ}
          tags:
            - name: kubernetes.io/cluster/${CLUSTER_ID}
              value: owned
          userDataSecret:
            name: worker-user-data
EOF
done

log_success "GPU MachineSets created (2x g6e.2xlarge with L4 GPUs)"

log_step "Deployment Complete"

echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
log_info "GPU node status:"
echo "  oc get machines -n openshift-machine-api | grep gpu"
echo "  oc get nodes -l node-role.kubernetes.io/gpu"
echo ""
