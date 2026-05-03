#!/usr/bin/env node

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const outDir = "docs/assets/architecture";

const stages = [
  ["010", "OpenShift AI Platform Foundation", "Establishes the shared OpenShift AI control plane, identity, GitOps, registry, and platform services"],
  ["020", "GPU Infrastructure for Private AI", "Adds the GPU-as-a-Service operating model: discovery, GPU enablement, Kueue queues, quota, autoscaling readiness, and observability"],
  ["030", "Private Model Serving", "Deploys private vLLM-backed and llm-d-ready model serving on Red Hat OpenShift AI"],
  ["040", "Governed Models-as-a-Service", "Introduces MaaS, subscriptions, API keys, gateway policy, quotas, limits, and telemetry"],
  ["050", "Approved External Model Access", "Registers approved external models behind the same governed MaaS access layer"],
  ["060", "MCP Context Integrations", "Adds MCP discovery and controlled context integrations for AI applications"],
  ["070", "Controlled Developer Workspaces", "Connects managed workspaces and coding assistants to governed model endpoints"],
  ["080", "AI-Assisted Application Modernization", "Connects MTA and Developer Lightspeed for MTA to MaaS for governed modernization assistance"],
  ["090", "Developer Portal and Self-Service", "Adds Developer Hub as the catalog and self-service entry point for the platform"],
];

const layers = [
  {
    label: ["Developer", "Experience"],
    y: 140,
    h: 150,
    cols: 5,
    boxW: 340,
    boxH: 82,
    caps: [
      { id: "devspaces", stage: "070", lines: ["Red Hat OpenShift", "Dev Spaces"] },
      { id: "continue", stage: "070", lines: ["Continue", "coding assistant"] },
      { id: "opencode", stage: "070", lines: ["OpenCode", "terminal agent"] },
      { id: "mta", stage: "080", lines: ["MTA and Developer", "Lightspeed for MTA"] },
      { id: "rhdh", stage: "090", lines: ["Red Hat", "Developer Hub"] },
    ],
  },
  {
    label: ["OpenShift AI", "and model", "platform"],
    y: 315,
    h: 330,
    cols: 7,
    boxW: 250,
    boxH: 82,
    caps: [
      { id: "dashboard", stage: "010", lines: ["OpenShift AI", "dashboard and", "GenAI Playground"] },
      { id: "projects", stage: "010", lines: ["Data science", "projects"] },
      { id: "registry", stage: "010", lines: ["Model registry", "and catalog"] },
      { id: "hardwareprofiles", stage: "010", lines: ["HardwareProfiles", "for workloads"] },
      { id: "kueue-integration", stage: "020", lines: ["OpenShift AI", "Kueue integration"] },
      { id: "private-serving", stage: "030", lines: ["Private model", "serving"] },
      { id: "vllm", stage: "030", lines: ["vLLM inference", "runtime"] },
      { id: "llmd", stage: "030", lines: ["llm-d scheduler", "and scale path"] },
      { id: "openai-api", stage: "030", lines: ["OpenAI-compatible", "API surface"] },
      { id: "maas", stage: "040", lines: ["Models-as-a-", "Service (MaaS)"] },
      { id: "maas-access", stage: "040", lines: ["Subscriptions,", "API keys,", "and telemetry"] },
      { id: "external-models", stage: "050", lines: ["Approved external", "model records"] },
      { id: "mcp", stage: "060", lines: ["MCP discovery", "and context servers"] },
      { id: "external-context", stage: "060", lines: ["Optional external", "context providers"] },
    ],
  },
  {
    label: ["GPU-as-a-", "Service", "accelerators"],
    y: 670,
    h: 180,
    cols: 7,
    boxW: 250,
    boxH: 82,
    caps: [
      { id: "nfd", stage: "020", lines: ["Node Feature", "Discovery"] },
      { id: "gpu-operator", stage: "020", lines: ["NVIDIA GPU", "Operator"] },
      { id: "machineset", stage: "020", lines: ["GPU worker", "MachineSets"] },
      { id: "resourceflavor", stage: "020", lines: ["Kueue", "ResourceFlavor"] },
      { id: "clusterqueue", stage: "020", lines: ["ClusterQueue", "GPU quota"] },
      { id: "localqueue", stage: "020", lines: ["LocalQueue", "private serving"] },
      { id: "dcgm-keda", stage: "020", lines: ["DCGM telemetry", "and KEDA readiness"] },
    ],
  },
  {
    label: ["OpenShift", "Container", "Platform"],
    y: 875,
    h: 290,
    cols: 5,
    boxW: 340,
    boxH: 82,
    caps: [
      { id: "gitops", stage: "010", lines: ["OpenShift GitOps", "(Argo CD)"] },
      { id: "operators", stage: "010", lines: ["Operators", "and CRDs"] },
      { id: "oauth", stage: "010", lines: ["OAuth, RBAC,", "and multitenancy"] },
      { id: "serverless", stage: "010", lines: ["OpenShift", "Serverless"] },
      { id: "mesh", stage: "010", lines: ["OpenShift", "Service Mesh"] },
      { id: "monitoring", stage: "010", lines: ["Monitoring", "(Prometheus)"] },
      { id: "routes", stage: "010", lines: ["Routes and", "ingress"] },
      { id: "secrets", stage: "010", lines: ["Secrets, config,", "and storage"] },
      { id: "gateway", stage: "040", lines: ["Connectivity Link", "and Gateway API"] },
      { id: "policy", stage: "040", lines: ["Authorino,", "Kuadrant, limits"] },
    ],
  },
  {
    label: ["Infrastructure", "and external", "services"],
    y: 1190,
    h: 150,
    cols: 5,
    boxW: 340,
    boxH: 82,
    caps: [
      { id: "cluster", stage: "010", lines: ["Cloud cluster"] },
      { id: "network", stage: "010", lines: ["Secured network"] },
      { id: "gpu-nodes", stage: "020", lines: ["GPU worker", "nodes"] },
      { id: "provider", stage: "050", lines: ["Approved external", "model provider"] },
      { id: "keycloak", stage: "080", lines: ["Red Hat build", "of Keycloak / OIDC"] },
    ],
  },
];

const colors = {
  bg: "#000000",
  panel: "#1f1f1f",
  rowStroke: "#4d4d4d",
  cap: "#242424",
  capRoot: "#383838",
  text: "#ffffff",
  muted: "#c7c7c7",
  red: "#ee0000",
  redDark: "#3f0000",
  redLight: "#f56e6e",
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function textLines(lines, x, y, size, fill, weight = 400, anchor = "middle", lineHeight = Math.round(size * 1.2)) {
  const firstY = y - ((lines.length - 1) * lineHeight) / 2;
  return lines
    .map((line, idx) => `<text x="${x}" y="${firstY + idx * lineHeight}" class="body" font-size="${size}" fill="${fill}" font-weight="${weight}" text-anchor="${anchor}">${esc(line)}</text>`)
    .join("\n");
}

function capStyle(cap, stageId, isRoot) {
  if (isRoot) {
    return {
      fill: colors.capRoot,
      stroke: colors.rowStroke,
      width: 2,
      text: colors.text,
      weight: 500,
      filter: "",
    };
  }

  if (cap.stage === stageId) {
    return {
      fill: colors.redDark,
      stroke: colors.red,
      width: 5,
      text: colors.text,
      weight: 700,
      filter: ' filter="url(#lift)"',
    };
  }

  return {
    fill: colors.cap,
    stroke: colors.rowStroke,
    width: 2,
    text: colors.muted,
    weight: 400,
    filter: "",
  };
}

function renderDiagram({ fileName, title, desc, stageId = null }) {
  const isRoot = stageId === null;
  const width = 2400;
  const height = 1450;
  const leftX = 36;
  const labelW = 315;
  const contentX = 390;
  const gap = 24;

  const svg = [];
  svg.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title desc">`);
  svg.push(`<title id="title">${esc(title)}</title>`);
  svg.push(`<desc id="desc">${esc(desc)}</desc>`);
  svg.push(`<style>.display{font-family:'Red Hat Display','Arial',sans-serif}.body{font-family:'Red Hat Text','Arial',sans-serif}.mono{font-family:'Red Hat Mono','Consolas',monospace}</style>`);
  svg.push(`<defs><radialGradient id="glow" cx="86%" cy="4%" r="70%"><stop offset="0" stop-color="${colors.red}" stop-opacity="0.14"/><stop offset="0.46" stop-color="${colors.red}" stop-opacity="0.04"/><stop offset="1" stop-color="#000000" stop-opacity="0"/></radialGradient><filter id="lift" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#000" flood-opacity="0.5"/></filter></defs>`);
  svg.push(`<rect width="${width}" height="${height}" fill="${colors.bg}"/>`);
  svg.push(`<rect width="${width}" height="${height}" fill="url(#glow)"/>`);
  svg.push(`<text x="64" y="74" class="display" font-size="50" fill="${colors.text}" font-weight="400">${stageId ? `<tspan fill="${colors.redLight}" font-weight="700">Stage ${stageId}:</tspan> ${esc(title.replace(`Stage ${stageId}: `, ""))}` : esc(title)}</text>`);
  svg.push(`<text x="64" y="116" class="body" font-size="25" fill="${colors.muted}">${esc(desc)}</text>`);

  for (const layer of layers) {
    svg.push(`<rect x="${leftX}" y="${layer.y}" width="${labelW}" height="${layer.h}" rx="2" fill="${colors.panel}"/>`);
    svg.push(textLines(layer.label, leftX + labelW / 2, layer.y + layer.h / 2 + 8, 30, colors.text, 700, "middle", 36));
    svg.push(`<rect x="${contentX - 20}" y="${layer.y}" width="${width - contentX - 54}" height="${layer.h}" rx="2" fill="none" stroke="${colors.rowStroke}" stroke-width="3"/>`);

    layer.caps.forEach((cap, idx) => {
      const row = Math.floor(idx / layer.cols);
      const col = idx % layer.cols;
      const x = contentX + col * (layer.boxW + gap);
      const y = layer.y + 34 + row * (layer.boxH + 26);
      const style = capStyle(cap, stageId, isRoot);
      svg.push(`<g${style.filter}><rect x="${x}" y="${y}" width="${layer.boxW}" height="${layer.boxH}" rx="2" fill="${style.fill}" stroke="${style.stroke}" stroke-width="${style.width}"/>`);
      const size = cap.lines.length > 2 ? 22 : 24;
      svg.push(textLines(cap.lines, x + layer.boxW / 2, y + layer.boxH / 2 + 8, size, style.text, style.weight, "middle", Math.round(size * 1.2)));
      svg.push(`</g>`);
    });
  }

  if (isRoot) {
    svg.push(`<g><rect x="540" y="1380" width="48" height="48" rx="2" fill="${colors.capRoot}" stroke="${colors.rowStroke}" stroke-width="2"/><text x="615" y="1411" class="body" font-size="26" fill="${colors.text}">Capability used in this workshop</text><text x="1170" y="1411" class="body" font-size="26" fill="${colors.muted}">Grouped by the platform layer that provides it</text></g>`);
  } else {
    svg.push(`<g><rect x="540" y="1380" width="48" height="48" rx="2" fill="${colors.redDark}" stroke="${colors.red}" stroke-width="5"/><text x="615" y="1411" class="body" font-size="26" fill="${colors.text}">New in this stage</text><rect x="970" y="1380" width="48" height="48" rx="2" fill="${colors.cap}" stroke="${colors.rowStroke}" stroke-width="2"/><text x="1045" y="1411" class="body" font-size="26" fill="${colors.text}">Capability shown for architectural context</text></g>`);
  }

  svg.push(`</svg>`);
  const path = join(outDir, fileName);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${svg.join("")}\n`);
}

renderDiagram({
  fileName: "rhoai-capability-map.svg",
  title: "Trusted enterprise AI development platform",
  desc: "Layered architecture with all platform capabilities used in this workshop",
});

for (const [stageId, name, desc] of stages) {
  renderDiagram({
    fileName: `stage-${stageId}-capability-map.svg`,
    title: `Stage ${stageId}: ${name}`,
    desc,
    stageId,
  });
}
