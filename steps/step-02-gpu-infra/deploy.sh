#!/usr/bin/env bash
# Step 02: GPU Infrastructure - Deploy Script
# Deploys GPU hardware enablement:
# - NFD Operator + NodeFeatureDiscovery instance
# - NVIDIA GPU Operator + ClusterPolicy + DCGM Dashboard
# - GPU MachineSets (AWS g6e.2xlarge)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-02-gpu-infra"

load_env
check_oc_logged_in

log_step "Step 02: GPU Infrastructure"

log_step "Checking prerequisites..."
if ! oc get applications -n openshift-gitops step-01-rhoai-platform &>/dev/null; then
    log_error "step-01-rhoai-platform Argo CD Application not found!"
    log_info "Please run: ./steps/step-01-rhoai-platform/deploy.sh first"
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

log_success "GPU MachineSets created (2x g6e.2xlarge with NVIDIA L4)"

log_step "Deployment Complete"

echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
log_info "GPU node status:"
echo "  oc get machines -n openshift-machine-api | grep gpu"
echo "  oc get nodes -l node-role.kubernetes.io/gpu"
echo ""
