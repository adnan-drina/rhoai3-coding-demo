# Agent sandboxes: create and qualify

`deploy.sh` stops at the platform: the OpenShell gateway, its identity and the `ai-agents` workspace with `ai-admin`
as its native administrator. These task scripts create and qualify the persistent OpenCode and Hermes sandboxes that
`ai-admin` owns there, and the developer's own OpenCode sandbox in `openshell-developer`, through the native OpenShell
API and the pinned CLI only. They are opt-in and never run by `deploy.sh` or `validate.sh`.

| Script | When to run |
|---|---|
| `create.sh opencode\|hermes --revision SHA` | Read-only check of an existing sandbox against its journal (provider, key, template, global policy, sandbox record). |
| `create.sh opencode\|hermes --revision SHA --apply [--expected-policy-hash HASH]` | Create the sandbox: provider profile, a 30-day MaaS key on the agent's dedicated subscription (`opencode-private-qwen38` / `hermes-private-qwen38`, held only by the native encrypted provider), the provider, the sandbox template, once the complete gateway-global policy (`global-policy.yaml`; only on an empty fleet with the reviewed current hash), then the sandbox and its start script, config and listener secret. |
| `create.sh opencode --owner ai-developer --revision SHA [--apply]` | The same for `ai-developer` in `openshell-developer`: subscription `opencode-developer-qwen38` (owned by the developer, who mints the key), the template and config in `opencode/developer/` (2 CPU, 4Gi, 8192 output tokens, no step limit). The developer is a workspace user, so the platform administrator session imports the profile and creates the provider and template; the developer creates and owns the sandbox. The global policy is shared and already set. Journal: `060-sandboxes/opencode-ai-developer/`. |
| `login.sh PROFILE_DIR` | Registers the gateway Route in a private CLI profile and signs a persona in (prints the Keycloak URL for a private window). Use the profile as that persona's `XDG_CONFIG_HOME` and as create.sh's `--persona-home`. |
| `qualify.sh opencode\|hermes --static` | Offline: the reviewed agent config and the independent fixture verifier. |
| `qualify.sh opencode\|hermes --run --revision SHA` | One synthetic coding task with one approved test command, an application cancellation and a native stop/start of the existing sandbox (model calls). Retains the key, sandbox, sessions and fixture. |
| `qualify.sh hermes --confinement-only --revision SHA` | No-model negative checks: denied filesystem writes, internet and metadata connections, the shared system Python, and wrong request methods or paths to MaaS. |
| `qualify.sh client --check --revision SHA --receipt FILE` | Owner-only client check of both agents: authenticated listener access through the native relay, missing and wrong credentials refused, reconnect keeps the retained identity. No model calls. |
| `qualify.sh inference --static\|--run DIR\|--cleanup DIR` | Temporary inference qualification as `ai-developer` in `openshell-developer`: one sandbox, one ephemeral key, a temporary global policy, all removed afterwards; `--cleanup` finishes an interrupted run from its journal. Needs `RHOAI_STAGE060_EXCLUSIVE_QUALIFICATION=true` and an empty fleet. |
| `qualify.sh host [DIR]` | Native host capability probe: one temporary namespace and restricted CPU Job with the pinned sandbox image, deleted afterwards. |

## Inputs

- `--revision`: the published commit `060-openshell-runtime` is Synced and Healthy at. The scripts compare their own
  published content (and the agent inputs below) with that commit and refuse a difference.
- The pinned CLI: `RHOAI_STAGE060_OPENSHELL_CLI`, default `~/.local/share/rhoai3-demo/openshell-<cliRelease>/bin/openshell`;
  its checksum must equal `cliBinarySha256` in `060-openshell-runtime/chart/source-pins.json`.
- `KUBECONFIG`: the private bootstrap (cluster-admin) kubeconfig; the project cluster guard applies.
- The genuine `ai-admin` sessions: `RHOAI_STAGE060_ADMIN_KUBECONFIG` (a private `oc login` kubeconfig) and
  `RHOAI_STAGE060_ADMIN_CLI_HOME` (the `XDG_CONFIG_HOME` of that persona's `openshell gateway login`), or
  `--persona-kubeconfig` and `--persona-home`. The inference suite uses the `ai-developer` equivalents
  `RHOAI_STAGE060_PERSONA_KUBECONFIG` and `RHOAI_STAGE060_PERSONA_CLI_HOME`.
- State: an owner-only journal per agent under `~/.local/state/rhoai3-coding-demo/060-sandboxes/<agent>/` (`--state-dir`,
  or `--state-root` for `client`). It records every created object, its digest and the key's metadata (never the key),
  plus the listener secret under `upload/state/auth/`. Keep it: reruns adopt only what it records, and rotation and
  rollback need it (docs/OPERATIONS.md, Stage 060).

## Developer access

The gateway is reachable from a laptop through the passthrough Route `openshell` in `openshell`; every call still
needs an OpenShell login. Its certificate does not name the Route host, so clients set
`OPENSHELL_GATEWAY_INSECURE=true` (demo posture) and `RUST_LOG=error`, which keeps the CLI's TLS warning off standard output. One-time setup by the platform team: `oc login` as `ai-developer`
into a private kubeconfig, `login.sh ~/.config/rhoai3-openshell-ai-developer` (sign in as `ai-developer`), set
`RHOAI_STAGE060_PERSONA_KUBECONFIG` and `RHOAI_STAGE060_PERSONA_CLI_HOME`, then
`create.sh opencode --owner ai-developer --revision SHA --apply`.

The developer then works with the pinned CLI and that profile (`export XDG_CONFIG_HOME=<profile>
OPENSHELL_GATEWAY_INSECURE=true RUST_LOG=error`):

| Step | Command |
|---|---|
| See the sandbox | `openshell --workspace openshell-developer sandbox list` (also under **AI hub → Agents** in the dashboard) |
| Bring code in (no Git egress in the sandbox) | `openshell --workspace openshell-developer sandbox upload opencode ./my-project /sandbox/workspace` (creates `/sandbox/workspace/my-project`; only files Git tracks or does not ignore, `--no-git-ignore` for all) |
| Open a shell and run OpenCode there | `openshell --workspace openshell-developer sandbox connect opencode`, then `cd /sandbox/workspace/my-project && opencode`. OpenCode reads its config from `/sandbox/workspace/opencode.json`, so start it under `/sandbox/workspace`. |
| Take results back | `openshell --workspace openshell-developer sandbox download opencode /sandbox/workspace/my-project ./my-project-out` |
| Stop or start it | `openshell --workspace openshell-developer sandbox stop\|start opencode` |

Inside the sandbox OpenCode reaches only MaaS (the global policy's `opencode_maas` route for `/usr/local/bin/opencode`),
writes only under `/sandbox`, and sees a placeholder instead of the MaaS key.

## Data

- `opencode/`, `hermes/`: per agent the provider profile, sandbox template, start script and agent config;
  `opencode/developer/` holds the developer sandbox's template and config.
- `global-policy.yaml`: the complete gateway-global policy both agents share (hard filesystem and Landlock denials,
  one MaaS route per agent binary). `__MAAS_COMMON_HOST__` is rendered from the live MaaS gateway at run time.
- `qualification/`: the inference suite's run profile and temporary policy, the no-network restore policy, the
  transport template it expects in `openshell-developer`, and the historical host capability receipt.
- `native.sh`: functions both scripts source (sessions, CLI, journal, setup steps); not run on its own.

Images are built separately: [../images/README.md](../images/README.md).
