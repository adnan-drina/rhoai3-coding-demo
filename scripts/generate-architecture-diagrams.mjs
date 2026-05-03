#!/usr/bin/env node

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const outDir = "docs/assets/architecture";

const stages = [
  ["010", "OpenShift AI Platform Foundation", "Establishes the shared OpenShift AI control plane, identity, GitOps, registry, and platform services"],
  ["020", "GPU Infrastructure for Private AI", "Adds the GPU-as-a-Service operating model: discovery, GPU enablement, Kueue queues, quota, autoscaling readiness, and observability"],
  ["030", "Private Model Serving", "Deploys private OpenAI-compatible model serving on Red Hat OpenShift AI"],
  ["040", "Governed Models-as-a-Service", "Introduces MaaS, subscriptions, API keys, gateway policy, quotas, limits, and telemetry"],
  ["050", "Approved External Model Access", "Registers approved external models behind the same governed MaaS access layer"],
  ["060", "MCP Context Integrations", "Adds MCP discovery and controlled context integrations for AI applications"],
  ["070", "Controlled Developer Workspaces", "Connects managed workspaces and coding assistants to governed model endpoints"],
  ["080", "AI-Assisted Application Modernization", "Connects MTA and Developer Lightspeed for MTA to MaaS for governed modernization assistance"],
  ["090", "Developer Portal and Self-Service", "Adds Developer Hub, software catalog, and Developer Lightspeed for RHDH to the developer layer"],
];

const colors = {
  black: "#000000",
  gray95: "#151515",
  gray90: "#1f1f1f",
  gray80: "#292929",
  gray70: "#383838",
  gray60: "#4d4d4d",
  gray30: "#c7c7c7",
  gray20: "#e0e0e0",
  white: "#ffffff",
  red: "#ee0000",
  purple: "#3d2785",
  teal: "#147878",
};

const products = {
  developerSuite: {
    label: ["Red Hat Advanced", "Developer Suite"],
    color: colors.purple,
  },
  openshiftAI: {
    label: ["Red Hat", "OpenShift AI"],
    color: colors.teal,
  },
  openshift: {
    label: ["Red Hat", "OpenShift"],
    color: colors.red,
  },
};

const rows = [
  {
    id: "developer",
    product: "developerSuite",
    label: ["Developer", "productivity", "and modernization"],
    y: 130,
    h: 210,
    cols: 3,
    caps: [
      { id: "devspaces", stage: "070", label: ["Red Hat OpenShift", "Dev Spaces"] },
      { id: "mta", stage: "080", label: ["Migration Toolkit", "for Applications"] },
      { id: "rhdh", stage: "090", label: ["Red Hat Developer Hub", "and software catalog"] },
      { id: "coding-assistants", stage: "070", label: ["Continue and OpenCode", "coding assistants"] },
      { id: "lightspeed-mta", stage: "080", label: ["Developer Lightspeed", "for MTA"] },
      { id: "lightspeed-rhdh", stage: "090", label: ["Developer Lightspeed", "for RHDH"] },
    ],
  },
  {
    id: "model-choices",
    product: "openshiftAI",
    label: ["Model and", "context choices"],
    y: 365,
    h: 160,
    cols: 5,
    caps: [
      { id: "private-models", stage: "030", label: ["Private local models", "on OpenShift"] },
      { id: "optimized-serving", stage: "030", label: ["Optimized", "model serving"] },
      { id: "openai-api", stage: "030", label: ["OpenAI-compatible", "APIs"] },
      { id: "external-models", stage: "050", label: ["Approved external", "models"] },
      { id: "external-context", stage: "060", label: ["Optional external", "context"] },
    ],
  },
  {
    id: "ai-governance",
    product: "openshiftAI",
    label: ["AI experiences", "and governed", "access"],
    y: 545,
    h: 230,
    cols: 4,
    caps: [
      { id: "control-plane", stage: "010", label: ["OpenShift AI", "control plane"] },
      { id: "genai-playground", stage: "010", label: ["Gen AI Studio", "and Playground"] },
      { id: "projects-rbac", stage: "010", label: ["Data science projects", "and RBAC"] },
      { id: "registry", stage: "010", label: ["Model catalog", "and registry"] },
      { id: "maas", stage: "040", label: ["Models-as-a-Service"] },
      { id: "maas-access", stage: "040", label: ["Subscriptions, API keys,", "quotas, telemetry"] },
      { id: "observability-governance", stage: "040", label: ["Model observability", "and governance"] },
      { id: "mcp", stage: "060", label: ["MCP discovery", "and context servers"] },
    ],
  },
  {
    id: "gpu-workloads",
    product: "openshiftAI",
    label: ["GPU acceleration", "and workload", "management"],
    y: 795,
    h: 170,
    cols: 3,
    caps: [
      { id: "hardware-profiles", stage: "010", label: ["Hardware and", "workload profiles"] },
      { id: "gpu-discovery", stage: "020", label: ["GPU discovery", "and enablement"] },
      { id: "gpu-capacity", stage: "020", label: ["GPU worker", "capacity"] },
      { id: "queue-quota", stage: "020", label: ["Queue, quota,", "admission control"] },
      { id: "gpu-telemetry", stage: "020", label: ["GPU telemetry and", "autoscaling readiness"] },
      { id: "distributed-inference", stage: "030", label: ["Distributed inference", "scale path"] },
    ],
  },
  {
    id: "platform-services",
    product: "openshift",
    label: ["Container", "platform", "services"],
    y: 995,
    h: 220,
    cols: 3,
    caps: [
      { id: "gitops", stage: "010", label: ["OpenShift GitOps", "and Argo CD"] },
      { id: "operators", stage: "010", label: ["Operators and", "lifecycle management"] },
      { id: "identity", stage: "010", label: ["Identity, RBAC,", "and multitenancy"] },
      { id: "serverless-mesh", stage: "010", label: ["Serverless and", "Service Mesh"] },
      { id: "gateway-policy", stage: "040", label: ["API connectivity", "and gateway policy"] },
      { id: "ops-services", stage: "010", label: ["Monitoring, routes,", "secrets, config, storage"] },
    ],
  },
  {
    id: "infrastructure",
    product: "openshift",
    label: ["Infrastructure", "and trust", "boundaries"],
    y: 1235,
    h: 150,
    cols: 4,
    caps: [
      { id: "cluster-network", stage: "010", label: ["Cloud cluster and", "secured network"] },
      { id: "gpu-nodes", stage: "020", label: ["GPU worker", "nodes"] },
      { id: "external-provider", stage: "050", label: ["Approved external", "model provider"] },
      { id: "keycloak", stage: "080", label: ["Red Hat build of", "Keycloak / OIDC"] },
    ],
  },
];

const layout = {
  width: 2400,
  height: 1460,
  productX: 140,
  productW: 210,
  rowX: 365,
  rowW: 250,
  contentX: 635,
  contentW: 1675,
  gap: 20,
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function textLines(lines, x, y, size, fill, weight = 400, anchor = "middle", lineHeight = Math.round(size * 1.18)) {
  const firstY = y - ((lines.length - 1) * lineHeight) / 2;
  return lines
    .map((line, idx) => `<text x="${x}" y="${firstY + idx * lineHeight}" class="body" font-size="${size}" fill="${fill}" font-weight="${weight}" text-anchor="${anchor}">${esc(line)}</text>`)
    .join("\n");
}

function rect({ x, y, w, h, fill, stroke = colors.gray70, strokeWidth = 2, rx = 2, opacity = null }) {
  const opacityAttr = opacity === null ? "" : ` opacity="${opacity}"`;
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"${opacityAttr}/>`;
}

function capStyle(cap, row, stageId, isRoot) {
  const productColor = products[row.product].color;

  if (!isRoot && cap.stage === stageId) {
    return {
      fill: colors.gray95,
      stroke: productColor,
      strokeWidth: 5,
      text: colors.white,
      weight: 700,
      filter: ' filter="url(#lift)"',
    };
  }

  return {
    fill: colors.gray80,
    stroke: colors.gray70,
    strokeWidth: 2,
    text: isRoot ? colors.white : colors.gray20,
    weight: isRoot ? 550 : 450,
    filter: "",
  };
}

function drawCapability(cap, row, idx, stageId, isRoot) {
  const cols = row.cols;
  const rowIndex = Math.floor(idx / cols);
  const colIndex = idx % cols;
  const boxW = (layout.contentW - 60 - layout.gap * (cols - 1)) / cols;
  const rowCount = Math.ceil(row.caps.length / cols);
  const boxH = Math.min(74, (row.h - 48 - layout.gap * (rowCount - 1)) / rowCount);
  const x = layout.contentX + 30 + colIndex * (boxW + layout.gap);
  const y = row.y + 24 + rowIndex * (boxH + layout.gap);
  const style = capStyle(cap, row, stageId, isRoot);
  const size = cap.label.length > 2 ? 18 : 19;

  return [
    `<g${style.filter}>`,
    rect({ x, y, w: boxW, h: boxH, fill: style.fill, stroke: style.stroke, strokeWidth: style.strokeWidth }),
    textLines(cap.label, x + boxW / 2, y + boxH / 2 + 7, size, style.text, style.weight, "middle"),
    "</g>",
  ].join("");
}

function drawRow(row, stageId, isRoot) {
  const product = products[row.product];
  const parts = [];

  parts.push(rect({ x: layout.rowX, y: row.y, w: layout.rowW, h: row.h, fill: product.color, stroke: product.color, strokeWidth: 0 }));
  parts.push(textLines(row.label, layout.rowX + layout.rowW / 2, row.y + row.h / 2 + 8, 22, colors.white, 700, "middle"));
  parts.push(rect({ x: layout.contentX, y: row.y, w: layout.contentW, h: row.h, fill: colors.gray90, stroke: colors.gray70, strokeWidth: 2 }));

  row.caps.forEach((cap, idx) => {
    parts.push(drawCapability(cap, row, idx, stageId, isRoot));
  });

  if (row.id === "developer") {
    parts.push(`<line x1="${layout.contentX + 30}" y1="${row.y + 106}" x2="${layout.contentX + layout.contentW - 30}" y2="${row.y + 106}" stroke="${colors.gray60}" stroke-width="2"/>`);
  }

  return parts.join("");
}

function drawProductRail() {
  const groups = [
    { product: "developerSuite", y: 130, h: 210 },
    { product: "openshiftAI", y: 365, h: 600 },
    { product: "openshift", y: 995, h: 390 },
  ];

  return groups
    .map(({ product, y, h }) => {
      const cfg = products[product];
      return [
        rect({ x: layout.productX, y, w: layout.productW, h, fill: cfg.color, stroke: cfg.color, strokeWidth: 0 }),
        textLines(cfg.label, layout.productX + layout.productW / 2, y + h / 2 + 8, 22, colors.white, 700, "middle"),
      ].join("");
    })
    .join("");
}

function drawLegend(stageId, isRoot) {
  const y = 1415;
  if (isRoot) {
    return [
      rect({ x: 720, y: y - 23, w: 34, h: 34, fill: colors.gray80, stroke: colors.gray70, strokeWidth: 2 }),
      `<text x="778" y="${y + 1}" class="body" font-size="22" fill="${colors.gray20}">Capability used in this workshop</text>`,
      `<text x="1180" y="${y + 1}" class="body" font-size="22" fill="${colors.gray30}">Left rail shows Red Hat product layer ownership</text>`,
    ].join("");
  }

  const stageProducts = new Set();
  rows.forEach((row) => {
    if (row.caps.some((cap) => cap.stage === stageId)) {
      stageProducts.add(row.product);
    }
  });
  const legendColor = products[[...stageProducts][0] || "openshiftAI"].color;

  return [
    rect({ x: 620, y: y - 23, w: 34, h: 34, fill: colors.gray95, stroke: legendColor, strokeWidth: 5 }),
    `<text x="678" y="${y + 1}" class="body" font-size="22" fill="${colors.gray20}">New in this stage</text>`,
    rect({ x: 965, y: y - 23, w: 34, h: 34, fill: colors.gray80, stroke: colors.gray70, strokeWidth: 2 }),
    `<text x="1023" y="${y + 1}" class="body" font-size="22" fill="${colors.gray20}">Capability shown for architectural context</text>`,
  ].join("");
}

function renderDiagram({ fileName, title, desc, stageId = null }) {
  const isRoot = stageId === null;
  const svg = [];

  svg.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" role="img" aria-labelledby="title desc">`);
  svg.push(`<title id="title">${esc(title)}</title>`);
  svg.push(`<desc id="desc">${esc(desc)}</desc>`);
  svg.push(`<style>.display{font-family:'Red Hat Display','Arial',sans-serif}.body{font-family:'Red Hat Text','Arial',sans-serif}</style>`);
  svg.push(`<defs><filter id="lift" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="5" flood-color="#000" flood-opacity="0.55"/></filter><filter id="panelShadow" x="-8%" y="-8%" width="116%" height="116%"><feDropShadow dx="0" dy="10" stdDeviation="9" flood-color="#000" flood-opacity="0.45"/></filter></defs>`);
  svg.push(`<g filter="url(#panelShadow)">`);
  svg.push(rect({ x: layout.productX, y: 26, w: layout.contentX + layout.contentW - layout.productX, h: 82, fill: colors.gray90, stroke: colors.gray70, strokeWidth: 2 }));
  svg.push(`<text x="${layout.width / 2}" y="60" class="display" font-size="42" fill="${colors.white}" font-weight="700" text-anchor="middle">${stageId ? `<tspan fill="${colors.gray30}" font-weight="500">Stage ${stageId}:</tspan> ${esc(title.replace(`Stage ${stageId}: `, ""))}` : esc(title)}</text>`);
  svg.push(`<text x="${layout.width / 2}" y="91" class="body" font-size="21" fill="${colors.gray30}" text-anchor="middle">${esc(desc)}</text>`);
  svg.push(drawProductRail());
  rows.forEach((row) => svg.push(drawRow(row, stageId, isRoot)));
  svg.push(drawLegend(stageId, isRoot));
  svg.push("</g>");
  svg.push("</svg>");

  const path = join(outDir, fileName);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${svg.join("")}\n`);
}

renderDiagram({
  fileName: "rhoai-capability-map.svg",
  title: "Trusted enterprise AI development platform",
  desc: "Red Hat Advanced Developer Suite, Red Hat OpenShift AI, and Red Hat OpenShift",
});

for (const [stageId, name, desc] of stages) {
  renderDiagram({
    fileName: `stage-${stageId}-capability-map.svg`,
    title: `Stage ${stageId}: ${name}`,
    desc,
    stageId,
  });
}
