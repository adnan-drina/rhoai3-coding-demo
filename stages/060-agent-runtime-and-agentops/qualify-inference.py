#!/usr/bin/env python3
"""Opt-in bounded inference qualification for the Stage 060 agent runtime.

Temporarily lets one OpenCode sandbox reach one governed MaaS model, proves a
generated, streamed reply and a cancelled generation, then restores the exact
original global policy. Never invoked by deploy.sh or validate.sh.

Usage:
  qualify-inference.py --run <private-evidence-directory>
  qualify-inference.py --cleanup <evidence-directory-of-an-interrupted-run>
  qualify-inference.py --static

Required environment for --run and --cleanup:
  RHOAI_EXPECTED_API_SERVER          shared cluster guard (see scripts/shared/lib.sh)
  RHOAI_STAGE060_OPENSHELL_CLI       openshell CLI matching source-pins.json cliBinarySha256
  RHOAI_STAGE060_PERSONA_KUBECONFIG  private `oc login` as ai-developer; owns the MaaS key
  RHOAI_STAGE060_PERSONA_CLI_HOME    XDG_CONFIG_HOME of that persona's `openshell gateway login`

Credential handling: the bootstrap client secret, the persona OpenShift token and
the MaaS key stay in memory. The bootstrap access token is written to a private
temporary CLI profile, because the CLI reads it from there, and is removed on exit.
The MaaS key is a one-hour ephemeral key and is revoked in the cleanup path.
"""
import base64
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(__file__).resolve().parent
PINS = ROOT / "gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json"
PROFILE_FILE = STAGE / "qualification/maas-qwen38-profile.yaml"
INFERENCE_POLICY = STAGE / "qualification/opencode-inference-policy.yaml"
TRANSPORT_POLICY = STAGE / "qualification/opencode-transport-policy.yaml"
HOST_PLACEHOLDER = "__MAAS_QWEN38_HOST__"
NS = "openshell"
PERSONA = "ai-developer"
WORKSPACE = "openshell-developer"
TEMPLATE = "oc-transport-11816"
SANDBOX = "oc-inference-check"
PROFILE = PROVIDER = "maas-qwen38"
MODEL = "qwen3-8-27b-int4"
MODEL_PATH = "/models-as-a-service/" + MODEL + "/v1"
DIRECTORY = "/sandbox/workspace"
TLS = ssl.create_default_context()
CLUSTER_ENV = None
OUTPUT_TOKEN_LIMIT = 128


class Failure(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise Failure(message)


def not_found(result):
    # Native NotFound only. Authentication, unavailable and timeouts are never absence.
    return result.returncode != 0 and bool(re.search(r'code: NotFound|status: NotFound|profile .* not found', result.stderr))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def interrupt(signum, frame):
    if signum == signal.SIGALRM:
        raise Failure('Qualification wall-clock deadline exceeded')
    raise KeyboardInterrupt('Termination requested')


def text_deltas(events, session, start=0, end=float('inf')):
    assistants = {p.get('info', {}).get('id') for _, kind, sid, p in events
                  if sid == session and kind == 'message.updated' and p.get('info', {}).get('role') == 'assistant'}
    parts = {p.get('part', {}).get('id') for _, kind, sid, p in events
             if sid == session and kind == 'message.part.updated' and p.get('part', {}).get('type') == 'text'
             and p.get('part', {}).get('messageID') in assistants}
    return [t for t, kind, sid, p in events if sid == session and start <= t <= end
            and kind == 'message.part.delta' and p.get('field') == 'text' and p.get('delta')
            and p.get('messageID') in assistants and p.get('partID') in parts]


def cancelled(generating, active_text, abort_status, aborted, outcome, status_http, statuses, session):
    info = (outcome.get('reply') or {}).get('info', {})
    return (generating and active_text and abort_status == 200 and aborted is True and
            outcome.get('status') == 200 and not outcome.get('transport') and
            (info.get('error') or {}).get('name') == 'MessageAbortedError' and
            status_http == 200 and isinstance(statuses, dict) and
            statuses.get(session, {}).get('type') == 'idle')


def verify_persona(identity, membership):
    expected = membership.get('members', [])
    need(not membership.get('next_page_token') and len(expected) == 1 and expected[0].get('role') == 'user',
         'Expected one curated normal-user membership')
    need(identity.get('subject') and identity.get('subject') == expected[0].get('subject') and
         identity.get('display_name') == PERSONA and 'openshell-user' in identity.get('roles', []) and
         'openshell-platform-admin' not in identity.get('roles', []), 'Persona subject/normal role differs from curated membership')


def generated_output(status, info, numbers):
    tokens = info.get('tokens', {}).get('output')
    return (status == 200 and not info.get('error') and info.get('role') == 'assistant' and
            info.get('providerID') == 'qwen38' and info.get('modelID') == MODEL and
            type(tokens) in (int, float) and 0 < tokens <= OUTPUT_TOKEN_LIMIT and numbers >= 20)


def oc(*args, kubeconfig=None, timeout=30):
    need(CLUSTER_ENV is not None, "Resolve the shared cluster guard before cluster reads")
    env = dict(CLUSTER_ENV, KUBECONFIG=kubeconfig) if kubeconfig else CLUSTER_ENV
    r = subprocess.run(["oc", "--request-timeout=20s", *args], env=env, capture_output=True, text=True, timeout=timeout)
    need(r.returncode == 0, "Bounded cluster request failed: " + " ".join(args[:2]))
    return r.stdout.strip()


def oc_json(*args):
    return json.loads(oc(*args, "-o", "json"))


def guard(kubeconfig=None):
    env = dict(CLUSTER_ENV or os.environ)
    if kubeconfig:
        env['KUBECONFIG'] = kubeconfig
    r = subprocess.run(["/bin/bash", "-c", 'export REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; '
                        'test -n "${RHOAI_EXPECTED_API_SERVER:-}"; check_oc_logged_in >&2; '
                        "python3 -c 'import json,os; print(json.dumps({\"KUBECONFIG\":os.environ.get(\"KUBECONFIG\",os.path.expanduser(\"~/.kube/config\")),\"RHOAI_EXPECTED_API_SERVER\":os.environ[\"RHOAI_EXPECTED_API_SERVER\"]}))'", "guard", str(ROOT)],
                       env=env, capture_output=True, text=True, timeout=30)
    need(r.returncode == 0, "Shared environment/login guard failed; RHOAI_EXPECTED_API_SERVER is required")
    # load_env diagnostics precede the final JSON; do not print the resolved context.
    return dict(env, **json.loads(r.stdout.strip().splitlines()[-1]))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http(url, token=None, body=None, method=None, form=None, timeout=30):
    """Return (status, parsed JSON or None). Never follows redirects."""
    headers = {}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    handlers = [NoRedirect()] + ([urllib.request.HTTPSHandler(context=TLS)] if url.startswith("https://") else [])
    try:
        with urllib.request.build_opener(*handlers).open(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, None


def describe(error):
    """Reviewed messages only; other exceptions are reduced to their class name."""
    return str(error) if isinstance(error, Failure) else error.__class__.__name__


def render(source, host, target):
    text = source.read_text()
    need(text.count(HOST_PLACEHOLDER) >= 1, source.name + " lost its host placeholder")
    target.write_text(text.replace(HOST_PLACEHOLDER, host))
    return target


def static():
    for source in (PROFILE_FILE, INFERENCE_POLICY):
        need(HOST_PLACEHOLDER in source.read_text(), source.name + " must keep the host placeholder")
        need(MODEL_PATH + "/chat/completions" in source.read_text(), source.name + " must name the reviewed chat path")
    need(HOST_PLACEHOLDER not in TRANSPORT_POLICY.read_text() and "network_policies: {}" in TRANSPORT_POLICY.read_text(),
         "The restore policy must stay the reviewed no-network policy")
    need(len(json.loads(PINS.read_text())["cliBinarySha256"]) == 64, "CLI pin is absent")
    print("[OK] Inference qualification inputs are consistent; no cluster or model call was made")


class Run:
    def __init__(self, evidence_dir):
        self.dir = Path(evidence_dir)
        self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        need(self.dir.stat().st_mode & 0o077 == 0, "Evidence directory must be private (mode 0700)")
        self.state_path = self.dir / "inference-state.json"
        need(not self.state_path.exists() or self.state_path.stat().st_mode & 0o077 == 0, 'Recovery journal must be private')
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        need(not self.state or re.fullmatch('[0-9a-f]{16}', self.state.get('runId', '')), 'Legacy/unowned journal requires reviewed manual recovery')
        self.evidence = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "persona": PERSONA,
                         "workspace": WORKSPACE, "model": MODEL, "checks": {}, "cleanup": {},
                         "scope": "one sandbox, one model, bounded prompts; no tool task, Hermes, catalog or tracing claim"}
        self.temp = Path(tempfile.mkdtemp(prefix="inference-", dir=self.dir))
        self.forward = self.service = None
        self.admin_exp = 0
        self.key = None
        self.lock = None
        self.sessions = []
        self.run_id = self.state.get('runId') or uuid.uuid4().hex[:16]
        self.sandbox = 'oc-inference-' + self.run_id
        self.provider = self.profile = 'maas-probe-' + self.run_id

    # ---- sessions -------------------------------------------------------
    def prepare(self):
        global CLUSTER_ENV
        CLUSTER_ENV = guard()
        cli = os.environ.get("RHOAI_STAGE060_OPENSHELL_CLI", "")
        need(cli and Path(cli).is_file(), "Set RHOAI_STAGE060_OPENSHELL_CLI to the pinned openshell CLI")
        pins = json.loads(PINS.read_text())
        need(hashlib.sha256(Path(cli).read_bytes()).hexdigest() == pins["cliBinarySha256"],
             "openshell CLI differs from source-pins.json cliBinarySha256")
        self.cli, self.pins = cli, pins
        kubeconfig = os.environ.get("RHOAI_STAGE060_PERSONA_KUBECONFIG", "")
        need(kubeconfig and Path(kubeconfig).is_file() and Path(kubeconfig).stat().st_mode & 0o077 == 0,
             "Set RHOAI_STAGE060_PERSONA_KUBECONFIG to a private existing ai-developer login")
        guard(kubeconfig)
        need(oc('whoami', '--show-server', kubeconfig=kubeconfig) == oc('whoami', '--show-server'),
             'Persona and guarded administrative context target different API servers')
        need(oc("whoami", kubeconfig=kubeconfig) == PERSONA, "Persona kubeconfig is not " + PERSONA)
        self.persona_token = oc("whoami", "-t", kubeconfig=kubeconfig)  # In memory only.
        self.persona_home = os.environ.get("RHOAI_STAGE060_PERSONA_CLI_HOME", "")
        gateway_name = (Path(self.persona_home) / "openshell/active_gateway").read_text().strip() if self.persona_home else ""
        metadata_path = Path(self.persona_home) / "openshell/gateways" / gateway_name / "metadata.json"
        need(gateway_name and metadata_path.is_file(), "Set RHOAI_STAGE060_PERSONA_CLI_HOME to an existing gateway login profile")
        self.gateway_name = gateway_name
        self.metadata = json.loads(metadata_path.read_text())
        endpoint = urllib.parse.urlsplit(self.metadata["gateway_endpoint"])
        need(endpoint.scheme == "https" and endpoint.hostname == "127.0.0.1" and endpoint.port, "Persona profile must use a local forwarded gateway endpoint")
        self.port = endpoint.port
        self.issuer = oc("get", "configmap", "openshell-identity", "-n", NS, "-o", "jsonpath={.data.issuer}")
        need(self.issuer.startswith("https://") and self.metadata.get("oidc_issuer") == self.issuer, "Persona profile issuer differs from the gateway issuer")
        lock_path = Path(tempfile.gettempdir()) / ('openshell-inference-' + hashlib.sha256(self.issuer.encode()).hexdigest()[:16] + '.lock')
        self.lock = os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600), 'w')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gateway = oc_json("get", "gateway.gateway.networking.k8s.io", "maas-default-gateway", "-n", "openshift-ingress")
        listeners = {l["name"]: l["hostname"] for l in gateway["spec"]["listeners"]}
        need("api" in listeners and "qwen3-8" in listeners, "MaaS gateway listeners are not the reviewed api/qwen3-8 pair")
        self.maas_api = "https://" + listeners["api"]
        self.model_host = listeners["qwen3-8"]
        self.chat_url = "https://" + self.model_host + MODEL_PATH + "/chat/completions"
        self.start_forward()
        who = self.persona(["whoami", "-o", "json"])
        need(who.returncode == 0, "Persona gateway session is absent or expired; run `openshell gateway login` again")
        identity = json.loads(who.stdout)
        need(identity.get("display_name") == PERSONA and "openshell-user" in identity.get("roles", []), "Gateway session is not the expected workspace user")
        self.admin_profile()
        members = self.admin(['workspace', 'member', 'list', '--workspace', WORKSPACE, '-o', 'json'])
        need(members.returncode == 0, 'Curated workspace membership read failed')
        membership = json.loads(members.stdout)
        verify_persona(identity, membership)
        need(self.state.get('subject', identity['subject']) == identity['subject'], 'Recovery journal belongs to a different immutable persona')
        self.save_state(runId=self.run_id, subject=identity['subject'])

    def resource(self, kind, name):
        result = self.admin([kind, 'list', '-o', 'json'], WORKSPACE)
        need(result.returncode == 0, 'Resource inventory failed; absence not established')
        value = json.loads(result.stdout)
        need(not value.get('next_page_token'), 'Resource inventory is paginated')
        found = [x for x in value[kind+'s'] if x.get('name') == name]
        need(len(found) <= 1, 'Ambiguous native resource identity')
        return found[0] if found else None

    def start_forward(self):
        def reachable():
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                return True
            except OSError:
                return False
        if reachable():
            return  # Reuse the operator's existing forward.
        self.forward = subprocess.Popen(["oc", "port-forward", "svc/openshell", f"{self.port}:8080", "-n", NS],
                                        env=CLUSTER_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 20
        while not reachable():
            need(time.monotonic() < deadline, "Gateway port-forward did not open")
            time.sleep(0.5)

    def admin_profile(self):
        self.admin_home = self.temp / "admin"
        directory = self.admin_home / "openshell/gateways" / self.gateway_name
        (directory / "mtls").mkdir(parents=True)
        ca = oc("get", "secret", "openshell-server-tls", "-n", NS, "-o", r"jsonpath={.data.ca\.crt}")
        (directory / "mtls/ca.crt").write_bytes(base64.b64decode(ca))  # Public CA certificate only.
        (directory / "metadata.json").write_text(json.dumps(dict(self.metadata, oidc_client_id="openshell-bootstrap")))
        (self.admin_home / "openshell/active_gateway").write_text(self.gateway_name)
        self.admin_token_path = directory / "oidc_token.json"
        self.refresh_admin()
        who = self.admin(["whoami", "-o", "json"])
        need(who.returncode == 0 and "openshell-platform-admin" in json.loads(who.stdout).get("roles", []), "Bootstrap identity is not a platform admin")

    def refresh_admin(self):
        secret = base64.b64decode(oc_json("get", "secret", "openshell-auth", "-n", "keycloak")["data"]["bootstrap-client-secret"]).decode()
        status, token = http(self.issuer + "/protocol/openid-connect/token",
                             form={"grant_type": "client_credentials", "client_id": "openshell-bootstrap", "client_secret": secret})
        need(status == 200 and token and token.get("access_token"), "Bootstrap token request failed")
        payload = token["access_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        audience = claims.get("aud") if isinstance(claims.get("aud"), list) else [claims.get("aud")]
        need(claims.get("iss") == self.issuer and "openshell-gateway" in audience
             and "openshell-platform-admin" in claims.get("realm_access", {}).get("roles", []), "Bootstrap token claims are not the reviewed admin identity")
        fd = os.open(self.admin_token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps({"access_token": token["access_token"], "expires_at": claims["exp"],
                                     "issuer": self.issuer, "client_id": "openshell-bootstrap"}))
        self.admin_exp = claims["exp"]

    def run_cli(self, home, args, workspace=None, env=None, timeout=90):
        command = [self.cli, "--gateway", self.gateway_name] + (["--workspace", workspace] if workspace else []) + args
        return subprocess.run(command, env=dict(os.environ, XDG_CONFIG_HOME=str(home), **(env or {})),
                              capture_output=True, text=True, timeout=timeout)

    def admin(self, args, workspace=None, env=None, timeout=90):
        if time.time() > self.admin_exp - 45:
            self.refresh_admin()
        return self.run_cli(self.admin_home, args, workspace, env, timeout)

    def persona(self, args, workspace=None, timeout=90):
        return self.run_cli(self.persona_home, args, workspace, None, timeout)

    def global_policy_hash(self):
        return self.global_policy()['hash']

    def global_policy(self):
        r = self.admin(["policy", "get", "--global", "--full", "-o", "json"])
        need(r.returncode == 0, "Global policy read failed")
        value = json.loads(r.stdout)
        need(value.get('hash') and isinstance(value.get('policy'), dict), 'Global policy payload/hash absent')
        return value

    def save_state(self, **fields):
        self.state.update(fields)
        pending = self.state_path.with_suffix('.pending')
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(self.state, indent=2) + "\n")  # Never credentials.
            output.flush()
            os.fsync(output.fileno())
        pending.replace(self.state_path)

    # ---- setup ----------------------------------------------------------
    def preconditions(self):
        need(os.environ.get('RHOAI_STAGE060_EXCLUSIVE_QUALIFICATION') == 'true',
             'Explicit exclusive gateway qualification window is required; global policy has no atomic CAS')
        sts = oc_json("get", "statefulset", "openshell", "-n", NS)
        need(sts["status"].get("readyReplicas") == 1 and sts["spec"]["template"]["spec"]["containers"][0]["image"].endswith(self.pins["images"]["gateway"]["amd64Digest"]),
             "Gateway is not ready on the pinned image")
        need(not oc_json("get", "sandboxes.agents.x-k8s.io", "-n", WORKSPACE)["items"], "Workspace already has a Sandbox; refusing to share the qualification window")
        fleet = self.admin(['sandbox', 'list', '--all-workspaces', '-o', 'json'])
        need(fleet.returncode == 0, 'All-workspace sandbox inventory failed')
        fleet = json.loads(fleet.stdout)
        need(not fleet.get('next_page_token') and fleet.get('sandboxes') == [], 'Global policy qualification requires an empty sandbox fleet')
        need(self.resource('provider', self.provider) is None, 'Run provider name exists')
        existing_profile = self.admin(['profile', 'export', self.profile, '-o', 'json'], WORKSPACE)
        need(not_found(existing_profile), 'Profile absence not established; refusing import')
        model = oc_json("get", "llminferenceservice", MODEL, "-n", "models-as-a-service")
        need(any(c["type"] == "Ready" and c["status"] == "True" for c in model["status"].get("conditions", [])), "Model is not Ready")
        templates = self.persona(["sandbox", "template", "list", "-o", "json"], WORKSPACE)
        need(templates.returncode == 0 and any(t["name"] == TEMPLATE for t in json.loads(templates.stdout)["templates"]), "Reviewed sandbox template is absent")
        original = self.global_policy()
        need(original['policy'].get('network_policies', {}) == {}, 'Qualification requires an existing no-network global policy')
        self.save_state(policyHashBefore=original['hash'], originalPolicy=original['policy'])

    def setup(self):
        profile = render(PROFILE_FILE, self.model_host, self.temp / "profile.yaml")
        profile.write_text(profile.read_text().replace('id: '+PROFILE, 'id: '+self.profile))
        policy = render(INFERENCE_POLICY, self.model_host, self.temp / "inference-policy.yaml")
        # The pinned native JSON serializer mirrors YAML and omits empty maps.
        # Preserve every original field; add only the reviewed route/binary stanza.
        try:
            import yaml
        except ImportError:
            raise Failure('Use a Python interpreter with PyYAML (also required by the native renderer)')
        authored = yaml.safe_load(policy.read_text())
        original = self.state['originalPolicy']
        need(original.get('filesystem_policy') == authored['filesystem_policy'] and original.get('landlock') == authored['landlock'],
             'Original hard filesystem policy differs from the reviewed qualification contract')
        intended = dict(original, network_policies=authored['network_policies'])
        policy.write_text(json.dumps(intended))
        need(self.admin(["profile", "lint", "-f", str(profile)], WORKSPACE).returncode == 0, "Gateway rejected the provider profile")
        self.save_state(profilePending=True)
        need(self.admin(["profile", "import", "-f", str(profile)], WORKSPACE).returncode == 0, "Provider profile import failed")
        exported = self.admin(['profile', 'export', self.profile, '-o', 'json'], WORKSPACE)
        need(exported.returncode == 0, 'Created profile read failed')
        self.save_state(profile=True, profilePending=False, profileDigest=digest(json.loads(exported.stdout)))
        need(self.global_policy_hash() == self.state['policyHashBefore'], 'Global policy changed before qualification')
        self.save_state(policyPending=True, intendedPolicy=intended)
        need(self.admin(["policy", "set", "--global", "--yes", "--policy", str(policy)]).returncode == 0, "Global policy update failed")
        applied = self.global_policy()
        need(applied['policy'] == intended, 'Global policy readback differs from exact intended content; refusing further operations')
        self.save_state(policy=True, policyPending=False, policyHashApplied=applied['hash'], appliedPolicy=applied['policy'])
        subscription = "personal-" + PERSONA
        status, subscriptions = http(self.maas_api + "/v1/subscriptions", self.persona_token)
        need(status == 200 and any(s.get("subscription_id_header") == subscription for s in subscriptions or []), "Persona cannot discover its MaaS subscription")
        self.save_state(keyPending=True)
        status, created = http(self.maas_api + "/v1/api-keys", self.persona_token,
                               {"name": "openshell-inference-" + self.run_id, "subscription": subscription, "expiresIn": "1h", "ephemeral": True})
        if status == 201 and isinstance(created, dict) and created.get('id'):
            self.save_state(keyId=created['id'], keyPending=False)
        need(status == 201 and created.get("id") and created.get("key") and created.get("ephemeral") is True, "Ephemeral MaaS key creation failed")
        self.key = created["key"]
        status, reply = http(self.chat_url, self.key, {"model": MODEL, "messages": [{"role": "user", "content": "Reply with exactly OK."}], "max_tokens": 8}, timeout=120)
        self.evidence["checks"]["directMaasCompletion"] = status == 200 and bool((reply or {}).get("choices"))
        need(self.evidence["checks"]["directMaasCompletion"], "MaaS refused a direct bounded completion with the new key (HTTP %s); the runtime path was not tested" % status)
        self.save_state(providerPending=True)
        created = self.admin(["provider", "create", "--name", self.provider, "--type", self.profile, "--credential", "MAAS_API_KEY"], WORKSPACE, {"MAAS_API_KEY": self.key})
        need(created.returncode == 0, "Provider creation failed")
        native = self.resource('provider', self.provider)
        need(native and native.get('id'), 'Created provider ID missing')
        self.save_state(provider=True, providerPending=False, providerId=native['id'])

    # ---- checks ---------------------------------------------------------
    def launch(self):
        config = {"$schema": "https://opencode.ai/config.json", "autoupdate": False, "share": "disabled", "enabled_providers": ["qwen38"],
                  "provider": {"qwen38": {"npm": "@ai-sdk/openai-compatible", "name": "MaaS Qwen3.8",
                                          "models": {MODEL: {"name": "Qwen3.8 27B INT4", "limit": {"context": 262144, "output": OUTPUT_TOKEN_LIMIT}}},
                                          "options": {"apiKey": "{env:MAAS_API_KEY}", "baseURL": "https://" + self.model_host + MODEL_PATH, "timeout": 60000}}},
                  "model": "qwen38/" + MODEL, "small_model": "qwen38/" + MODEL,
                  "permission": {"edit": "deny", "bash": "deny", "webfetch": "deny"}}
        encoded = base64.b64encode(json.dumps(config).encode()).decode()
        command = ("mkdir -p /sandbox/state /sandbox/tmp /sandbox/workspace && cd /sandbox/workspace && echo " + encoded +
                   " | base64 -d > opencode.json && export OPENCODE_DISABLE_MODELS_FETCH=1 OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=128 && exec opencode serve --hostname 127.0.0.1 --port 4096")
        self.save_state(sandboxPending=True)
        created = self.persona(["sandbox", "create", "--name", self.sandbox, "--template", TEMPLATE, "--provider", self.provider, "--no-auto-providers",
                                "--approval-mode", "manual", "--detach", "-o", "json", "--", "/bin/bash", "-c", command], WORKSPACE, 240)
        need(created.returncode == 0, "Sandbox creation with the provider failed")
        resource = self.persona(['sandbox', 'get', self.sandbox, '-o', 'json'], WORKSPACE)
        need(resource.returncode == 0, 'Created sandbox identity read failed')
        native = json.loads(resource.stdout)
        need(native.get('id'), 'Created sandbox has no native ID')
        self.save_state(sandbox=True, sandboxPending=False, sandboxId=native['id'])
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.local = probe.getsockname()[1]
        self.service = subprocess.Popen([self.cli, "--gateway", self.gateway_name, "--workspace", WORKSPACE, "forward", "service", self.sandbox,
                                         "--target-port", "4096", "--target-host", "127.0.0.1", "--local", f"127.0.0.1:{self.local}"],
                                        env=dict(os.environ, XDG_CONFIG_HOME=str(self.persona_home)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 90
        while True:
            try:
                status, health = self.opencode("GET", "/global/health", timeout=5)
                if status == 200 and (health or {}).get("healthy"):
                    break
            except OSError:
                pass
            need(time.monotonic() < deadline, "OpenCode did not become healthy through the forward")
            time.sleep(2)

    def opencode(self, method, path, body=None, timeout=30):
        separator = "&" if "?" in path else "?"
        url = f"http://127.0.0.1:{self.local}{path}{separator}directory={urllib.parse.quote(DIRECTORY, safe='')}"
        return http(url, body=body, method=method, timeout=timeout)

    def sandbox_python(self, program, timeout=40):
        r = self.persona(["sandbox", "exec", "--name", self.sandbox, "--timeout", str(timeout), "--no-tty", "--no-login-shell", "--", "/usr/bin/python3", "-c", program], WORKSPACE, timeout + 20)
        need(r.returncode == 0 and r.stdout.strip(), "Sandbox probe failed")
        return json.loads(r.stdout.strip().splitlines()[-1])

    def events(self, stop, seen):
        """Collect (monotonic time, event type, session id) from the OpenCode event stream."""
        url = f"http://127.0.0.1:{self.local}/event?directory={urllib.parse.quote(DIRECTORY, safe='')}"
        try:
            with urllib.request.urlopen(url, timeout=300) as stream:
                while not stop.is_set():
                    line = stream.readline()
                    if not line:
                        return
                    if line.startswith(b"data:"):
                        try:
                            event = json.loads(line[5:])
                        except ValueError:
                            continue
                        properties = event.get("properties", {})
                        session = properties.get("sessionID") or properties.get("part", {}).get("sessionID") or properties.get("info", {}).get("sessionID")
                        seen.append((time.monotonic(), event.get("type", ""), session, properties))
        except OSError as error:
            self.evidence['checks']['eventTransportError'] = error.__class__.__name__

    def prompt(self, session, text, timeout=90):
        body = {"model": {"providerID": "qwen38", "modelID": MODEL}, "parts": [{"type": "text", "text": text}]}
        return self.opencode("POST", f"/session/{session}/message", body, timeout)

    def checks(self):
        results = self.evidence["checks"]
        probe = self.sandbox_python("import os,hashlib,json;v=os.environ.get('MAAS_API_KEY','');print(json.dumps({'present':bool(v),'sha256':hashlib.sha256(v.encode()).hexdigest()}))")
        results["sandboxHoldsPlaceholderNotKey"] = probe["present"] and probe["sha256"] != hashlib.sha256(self.key.encode()).hexdigest()
        effective = self.persona(["policy", "get", self.sandbox, "--full"], WORKSPACE)
        results["effectivePolicyNamesReviewedEndpoint"] = effective.returncode == 0 and self.model_host in effective.stdout and "chat/completions" in effective.stdout
        stop, seen = threading.Event(), []
        reader = threading.Thread(target=self.events, args=(stop, seen), daemon=True)
        reader.start()
        deadline = time.monotonic() + 10
        while not seen and time.monotonic() < deadline:
            time.sleep(0.2)
        try:
            status, session = self.opencode("POST", "/session", {})
            need(status == 200 and session.get("id"), "OpenCode session creation failed")
            self.sessions.append(session['id'])
            started = time.monotonic()
            status, reply = self.prompt(session["id"], "Count from 1 to 30, separated by commas. Output only the numbers.")
            finished = time.monotonic()
            info = (reply or {}).get("info", {})
            text = "".join(p.get("text", "") for p in (reply or {}).get("parts", []) if p.get("type") == "text")
            parts = text_deltas(seen, session['id'], started, finished)
            results["generated"] = {"httpStatus": status, "error": (info.get("error") or {}).get("name"), "provider": info.get("providerID"), "modelID": info.get("modelID"),
                                    "replyCharacters": len(text), "numbersInReply": sum(token.strip().isdigit() for token in text.replace("\n", ",").split(",")),
                                    "outputTokens": info.get("tokens", {}).get("output", 0)}
            results["generatedOutput"] = generated_output(status, info, results['generated']['numbersInReply'])
            results["streaming"] = {"partEvents": len(parts), "spanSeconds": round(parts[-1] - parts[0], 3) if parts else 0,
                                    "firstEventBeforeCompletionSeconds": round(finished - parts[0], 3) if parts else 0}
            results["streamedIncrementally"] = len(parts) >= 2 and parts[0] < finished and not results.get('eventTransportError')
            # Cancellation: abort a long generation after its first streamed parts.
            status, second = self.opencode("POST", "/session", {})
            need(status == 200 and second.get("id"), "Second OpenCode session creation failed")
            self.sessions.append(second['id'])
            outcome = {}
            def long_prompt():
                try:
                    outcome["status"], outcome["reply"] = self.prompt(second["id"], "Explain a Java null check in a short paragraph.", 90)
                except OSError as error:
                    outcome["transport"] = error.__class__.__name__
            worker = threading.Thread(target=long_prompt, daemon=True)
            worker.start()
            deadline = time.monotonic() + 30
            while not text_deltas(seen, second['id']) and time.monotonic() < deadline and worker.is_alive():
                time.sleep(0.3)
            busy_status, busy = self.opencode('GET', '/session/status')
            generating = worker.is_alive() and busy_status == 200 and isinstance(busy, dict) and busy.get(second['id'], {}).get('type') == 'busy'
            active_text = bool(text_deltas(seen, second['id']))
            need(generating and active_text, 'No active assistant generation to cancel')
            aborted_at = time.monotonic()
            status, aborted = self.opencode("POST", f"/session/{second['id']}/abort")
            worker.join(timeout=45)
            error = ((outcome.get("reply") or {}).get("info", {}).get("error") or {}).get("name")
            status_http, statuses = self.opencode("GET", "/session/status")
            results["cancellation"] = {"wasGenerating": generating, "abortAccepted": status == 200 and aborted is True, "promptReturned": not worker.is_alive(),
                                       "returnSeconds": round(time.monotonic() - aborted_at, 3), "error": error,
                                       "idleAfterwards": status_http == 200 and isinstance(statuses, dict) and statuses.get(second['id'], {}).get('type') == 'idle'}
            settled = time.monotonic()
            time.sleep(1)
            results["taskCancelled"] = (not worker.is_alive() and cancelled(generating, active_text, status, aborted, outcome, status_http, statuses, second['id'])
                                        and not text_deltas(seen, second['id'], settled) and not results.get('eventTransportError'))
        finally:
            stop.set()
        denied = self.sandbox_python(
            "import json,socket\nr={}\n"
            "def attempt(key,host):\n"
            "    s=socket.socket();s.settimeout(8)\n"
            "    try:\n        s.connect((host,443));r[key]=False\n"
            "    except OSError as e:\n        r[key]=e.errno in (1,13);r[key+'Errno']=e.errno\n"
            "    finally:\n        s.close()\n"
            "attempt('internetDenied','1.1.1.1')\n"
            f"attempt('otherBinaryToModelDenied',{self.model_host!r})\n"
            "print(json.dumps(r))")
        results["egressStillConfined"] = denied
        results["confinementHeld"] = denied.get("internetDenied") is True and denied.get("otherBinaryToModelDenied") is True

    # ---- cleanup --------------------------------------------------------
    def cleanup(self):
        done = self.evidence["cleanup"]
        steps = []
        def step(name, action):
            steps.append(name)
            try:
                done[name] = bool(action())
            except Exception as error:  # Every step is attempted; failures are reported, not hidden.
                done[name] = False
                done[name + "Error"] = error.__class__.__name__
        def close_process(process):
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            return True
        for session in self.sessions:
            step('sessionAbort-'+str(self.sessions.index(session)),
                 lambda session=session: self.opencode('POST', '/session/'+session+'/abort', timeout=5) == (200, True))
        step('serviceClosed', lambda: close_process(self.service))
        for pending in ('sandboxPending', 'providerPending', 'profilePending', 'policyPending', 'keyPending'):
            if self.state.get(pending):
                # A lost creation/update response does not establish ownership or applied hash.
                done[pending] = False
                steps.append(pending)
        if self.state.get("sandbox"):
            def delete_sandbox():
                resource = self.resource('sandbox', self.sandbox)
                if resource is None:
                    return True
                need(resource.get('id') == self.state.get('sandboxId'), 'Sandbox identity changed; refusing deletion')
                need(self.persona(["sandbox", "delete", self.sandbox], WORKSPACE, 120).returncode == 0, 'Native sandbox deletion failed')
                deadline = time.monotonic() + 120
                while self.resource('sandbox', self.sandbox) is not None:
                    need(time.monotonic() < deadline, "Sandbox resources remain")
                    time.sleep(5)
                return True
            step("sandboxDeleted", delete_sandbox)
        if self.state.get("provider"):
            def delete_provider():
                resource = self.resource('provider', self.provider)
                if resource is None:
                    return True
                need(resource.get('id') == self.state.get('providerId'), 'Provider identity changed; refusing deletion')
                need(self.admin(['provider', 'delete', self.provider], WORKSPACE).returncode == 0, 'Provider deletion failed')
                return self.resource('provider', self.provider) is None
            step("providerDeleted", delete_provider)
        if self.state.get("profile"):
            def delete_profile():
                current = self.admin(['profile', 'export', self.profile, '-o', 'json'], WORKSPACE)
                if not_found(current):
                    return True
                need(current.returncode == 0 and digest(json.loads(current.stdout)) == self.state.get('profileDigest'),
                     'Profile read/identity changed; refusing deletion')
                need(self.admin(['profile', 'delete', self.profile], WORKSPACE).returncode == 0, 'Profile deletion failed')
                return not_found(self.admin(['profile', 'export', self.profile, '-o', 'json'], WORKSPACE))
            step("profileDeleted", delete_profile)
        if self.state.get("policy"):
            def restore():
                current = self.global_policy_hash()
                if current == self.state.get('policyHashBefore'):
                    done['policyHashEqualsBefore'] = True
                    return True
                need(current == self.state.get('policyHashApplied'), 'Concurrent global policy change; refusing overwrite')
                restore_file = self.temp / 'original-policy.json'
                restore_file.write_text(json.dumps(self.state['originalPolicy']))
                need(self.admin(["policy", "set", "--global", "--yes", "--policy", str(restore_file)]).returncode == 0, "Policy restore failed")
                done["policyHashEqualsBefore"] = self.global_policy_hash() == self.state.get("policyHashBefore")
                need(done['policyHashEqualsBefore'], 'Restored global policy hash mismatch')
                return done['policyHashEqualsBefore']
            step("noNetworkPolicyRestored", restore)
        if self.state.get("keyId"):
            def revoke():
                status, revoked = http(self.maas_api + "/v1/api-keys/" + urllib.parse.quote(self.state["keyId"], safe=""), self.persona_token, method="DELETE")
                need(status == 200 and revoked.get("status") == "revoked", "Key revocation was not confirmed")
                if self.key:
                    status, _ = http(self.chat_url, self.key, {"model": MODEL, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 4}, timeout=60)
                    done["revokedKeyDenied"] = status in (401, 403)
                return True
            step("keyRevoked", revoke)
        step('gatewayForwardClosed', lambda: close_process(self.forward))
        shutil.rmtree(self.temp, ignore_errors=True)  # Removes the temporary admin profile and rendered files.
        if self.lock:
            self.lock.close()
        return all(done[name] for name in steps) and done.get("revokedKeyDenied", True)

    def finish(self, failure, clean):
        required = ["directMaasCompletion", "sandboxHoldsPlaceholderNotKey", "effectivePolicyNamesReviewedEndpoint", "generatedOutput",
                    "streamedIncrementally", "taskCancelled", "confinementHeld"]
        self.evidence["passed"] = failure is None and clean and all(self.evidence["checks"].get(k) is True for k in required)
        if failure:
            self.evidence["failure"] = describe(failure)
        if clean:
            self.state_path.unlink(missing_ok=True)
        path = self.dir / ("inference-results-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(self.evidence, indent=2) + "\n")
        print(json.dumps({"passed": self.evidence["passed"], "checks": {k: self.evidence["checks"].get(k) for k in required}, "cleanup": self.evidence["cleanup"]}, indent=2))
        print("Sanitized evidence saved to " + str(path) + "; no tokens, keys, hostnames or reply text included")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--static":
        return static()
    if len(sys.argv) != 3 or sys.argv[1] not in ("--run", "--cleanup"):
        print(__doc__)
        raise SystemExit(2)
    state = Path(sys.argv[2]) / "inference-state.json"
    need(sys.argv[1] == "--cleanup" or not state.exists(), "A previous run left state in this directory; use --cleanup first")
    run = Run(sys.argv[2])
    failure = None
    old_signals = {s: signal.signal(s, interrupt) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM)}
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 240)
    clean = False
    try:
        run.prepare()
        if sys.argv[1] == "--run":
            run.preconditions()
            run.setup()
            run.launch()
            run.checks()
        else:
            need(run.state, "No interrupted-run state in this directory")
    except (Exception, KeyboardInterrupt) as error:
        failure = error
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        # A second INT/TERM must not interrupt best-effort teardown; SIGKILL cannot be handled.
        for s in old_signals:
            signal.signal(s, signal.SIG_IGN)
        try:
            clean = run.cleanup()
        except (Exception, KeyboardInterrupt) as error:
            failure = failure or error
        finally:
            run.finish(failure, clean)
            for s, handler in old_signals.items():
                signal.signal(s, handler)
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
    if failure or not clean or not (run.evidence["passed"] or sys.argv[1] == "--cleanup"):
        raise SystemExit("[FAIL] " + (describe(failure) if failure else "see sanitized evidence"))
    print("[PASS] Bounded inference qualification" if sys.argv[1] == "--run" else "[OK] Interrupted run cleaned up")


if __name__ == "__main__":
    try:
        main()
    except Failure as error:
        raise SystemExit("[FAIL] " + str(error))
