#!/usr/bin/env python3
"""Build and baseline an rgctl policy for the migrated application.

Measures first, then chooses thresholds. Nothing here is copied from the blog:
the domains come from this application's own package layout, and every number is
taken from this graph.

Usage:
  python3 policy/build-policy.py --measure      # baseline only, writes baseline.json
  python3 policy/build-policy.py --write        # also writes policy.json
"""
import argparse, collections, json, pathlib, subprocess, sys

APP = pathlib.Path("/Users/adrina/Sandbox/rgctl-experiment/app")
RG = "/Users/adrina/Sandbox/rgctl-experiment/_tools/rgctl"
OUT = pathlib.Path(__file__).resolve().parent

# The application's own package layout is the domain map. No literal class or
# method name of this specimen appears anywhere in this file.
DOMAIN_OF_PACKAGE_SEGMENT = [
    ("repository", "repository"),
    ("service", "service"),
    ("rest", "rest"),
    ("mapper", "mapper"),
    ("model", "model"),
    ("security", "security"),
    ("util", "util"),
]


def rg(*args):
    p = subprocess.run([RG, "-r", str(APP), *args], capture_output=True, text=True)
    return p.stdout


def export_graph():
    tmp = OUT / "_graph.json"
    rg("export", "--export-format", "json", "--export-output", str(tmp))
    return json.loads(tmp.read_text())


def domain_for(file_path):
    if file_path is None or "/src/main/java/" not in file_path:
        return None
    rel = file_path.split("/src/main/java/", 1)[1]
    segments = rel.split("/")[:-1]
    for segment, domain in DOMAIN_OF_PACKAGE_SEGMENT:
        if segment in segments:
            return domain
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    g = export_graph()
    nodes = {n["id"]: n for n in g["nodes"]}
    node_domains = {}
    for nid, n in nodes.items():
        d = domain_for(n.get("file_path"))
        if d:
            node_domains[nid] = d

    per_domain = collections.Counter(node_domains.values())

    # --- baseline: which domain pairs are actually connected today ---
    crossings = collections.Counter()
    examples = collections.defaultdict(list)
    for e in g["edges"]:
        a, b = node_domains.get(e["from"]), node_domains.get(e["to"])
        if not a or not b or a == b:
            continue
        crossings[(a, b, e["edge_type"])] += 1
        if len(examples[(a, b)]) < 3:
            na, nb = nodes[e["from"]], nodes[e["to"]]
            examples[(a, b)].append(
                f'{na.get("qualified_name") or na.get("name")} -[{e["edge_type"]}]-> '
                f'{nb.get("qualified_name") or nb.get("name")}')

    # --- baseline: centrality ---
    bet = json.loads(_json_of(rg("-f", "json", "metrics", "--betweenness")))
    scores = [r["score"] for r in bet.get("betweenness", [])]
    max_bet = max(scores) if scores else 0.0

    baseline = {
        "nodes_total": len(nodes),
        "nodes_mapped_to_a_domain": len(node_domains),
        "nodes_per_domain": dict(per_domain),
        "directed_domain_crossings": {f"{a}->{b} [{t}]": c for (a, b, t), c in sorted(crossings.items())},
        "crossing_examples": {f"{a}->{b}": v for (a, b), v in sorted(examples.items())},
        "max_betweenness": max_bet,
        "betweenness_top10": bet.get("betweenness", [])[:10],
    }
    (OUT / "baseline.json").write_text(json.dumps(baseline, indent=2, sort_keys=True))
    print("baseline ->", OUT / "baseline.json")
    print("  nodes:", len(nodes), " mapped:", len(node_domains))
    print("  per domain:", dict(per_domain))
    print("  max betweenness:", max_bet)
    print("  directed crossings observed:")
    for k, v in sorted(baseline["directed_domain_crossings"].items()):
        print(f"      {v:5d}  {k}")

    if args.write:
        policy = {
            "forbidden_crossings": [["rest", "repository"]],
            "node_domains": node_domains,
        }
        (OUT / "policy.json").write_text(json.dumps(policy, indent=2, sort_keys=True))
        print("policy ->", OUT / "policy.json")


def _json_of(text):
    return text[text.index("{"):text.rindex("}") + 1]


if __name__ == "__main__":
    sys.exit(main())
