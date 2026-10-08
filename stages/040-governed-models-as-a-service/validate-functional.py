#!/usr/bin/env python3
"""Explicit bounded MaaS functional check, never invoked by deployment polling.

Creates one synthetic expiring key, revokes only that key in finally. No model
or workload creation, provider-key access, browser operation or load test.
API contract: shipped MaaS 563117f178f04c8eac7058df481815a97694a88d/openapi3.yaml.
"""
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
from urllib.parse import quote, urlencode, urlsplit
import urllib.error
import urllib.request
import uuid

import importlib.util
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("native", Path(__file__).with_name("validate-native.py"))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class Pending(RuntimeError):
    pass


class HTTPFailure(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__("Authenticated native API returned unexpected HTTP status " + str(status))


def need(value, message):
    native.need(value, message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer credential to a redirected endpoint.


def request(url, context, token=None, body=None, method=None, native_messages=False):
    headers = {"Accept": "application/json"}
    if token:
        headers["x-api-key" if native_messages else "Authorization"] = token if native_messages else "Bearer " + token
    if native_messages:
        headers["anthropic-version"] = "2023-06-01"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method=method)
    try:
        return urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context)).open(req, timeout=90)
    except urllib.error.HTTPError as error:
        return error
    except Exception:
        raise RuntimeError("Verified TLS API request did not complete") from None


def api(url, context, token, body=None, method=None, expected=200):
    with request(url, context, token, body, method) as response:
        if response.status != expected:
            raise HTTPFailure(response.status)
        return json.loads(response.read(2 * 1024 * 1024))


def completion_url(endpoint):
    parsed = urlsplit(endpoint)
    need(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password,
         "Native catalog endpoint is not verified HTTPS")
    base = endpoint.rstrip("/")
    return base + ("/chat/completions" if parsed.path.rstrip("/").endswith("/v1") else "/v1/chat/completions")


def catalog_id(ref, desired):
    model_ref = ref["spec"]["modelRef"]
    if model_ref.get("kind") == "ExternalModel":
        return model_ref["name"]
    need(model_ref.get("kind", "llmisvc") in ("llmisvc", "LLMInferenceService"),
         "Reviewed model reference kind is unsupported")
    namespace = ref["metadata"]["namespace"]
    models = [o for o in desired if o["kind"] == "LLMInferenceService" and
              o["metadata"]["namespace"] == namespace and
              o["metadata"]["name"] == model_ref["name"]]
    need(len(models) == 1, "Reviewed local model reference is not unique")
    expected = "publishers/" + namespace + "/models/" + models[0]["spec"]["model"]["name"]
    current = native.get("maasmodelrefs.maas.opendatahub.io", ref["metadata"]["name"], namespace)
    need(current.get("status", {}).get("resolvedModelAlias") == expected,
         "Native local model alias differs from reviewed model and namespace")
    return expected


def read_sse(response, clock=time.monotonic):
    need(response.status == 200 and "text/event-stream" in response.headers.get("Content-Type", ""),
         "Native stream response is not successful SSE")
    fragments, usage, done, times, size = [], None, False, [], 0
    start = clock()
    for raw in response:
        size += len(raw)
        need(size <= 2 * 1024 * 1024 and clock() - start <= 120, "SSE response exceeded bounded limits")
        if not raw.startswith(b"data:"):
            continue
        payload = raw[5:].strip()
        if payload == b"[DONE]":
            done = True
            break
        item = json.loads(payload)
        need(not item.get("error"), "SSE stream reports provider error")
        if item.get("usage"):
            usage = item["usage"]
        for choice in item.get("choices", []):
            delta = choice.get("delta", {})
            value = delta.get("content") or delta.get("reasoning_content")
            if value:
                fragments.append(value)
                times.append(clock() - start)
    need(done and usage and usage.get("total_tokens", 0) > 0, "SSE terminal marker or usage is absent")
    need(len(times) >= 2 and times[-1] - times[0] >= 0.02,
         "Incremental SSE delivery is not demonstrated (buffered or insufficient chunks)")
    return {"content_chunks": len(times), "delivery_span_seconds": round(times[-1] - times[0], 3),
            "total_tokens": usage["total_tokens"],
            "response_sha256": hashlib.sha256("".join(fragments).encode()).hexdigest()}


def read_messages_sse(response, expected_model):
    need(response.status == 200 and "text/event-stream" in response.headers.get("Content-Type", ""), "Native Messages response is not successful SSE")
    started = time.monotonic(); size = 0; deltas = 0; model = None; usage = {}; stopped = False; times = []
    for raw in response:
        size += len(raw)
        need(size <= 1024 * 1024 and time.monotonic() - started <= 90, "Native Messages stream exceeds bounded scope")
        if not raw.startswith(b"data:"): continue
        event = json.loads(raw[5:].strip())
        need(event.get("type") != "error", "Native Messages returned a provider error")
        if event.get("type") == "message_start":
            message = event["message"]; model = message.get("model"); usage.update(message.get("usage", {}))
        elif event.get("type") == "content_block_delta" and event.get("delta", {}).get("type") == "text_delta":
            if event["delta"].get("text"): deltas += 1; times.append(time.monotonic())
        elif event.get("type") == "message_delta": usage.update(event.get("usage", {}))
        elif event.get("type") == "message_stop": stopped = True
    need(model == expected_model and stopped and deltas > 0 and isinstance(usage.get("input_tokens"), int) and usage["input_tokens"] >= 0 and isinstance(usage.get("output_tokens"), int) and 0 < usage["output_tokens"] <= 32, "Native Messages identity, deltas, final usage or stop event absent")
    need(len(times) > 1, "Multiple native Messages text deltas were not observed")
    return {"provider_model": model, "content_block_deltas": deltas, "message_stop": True, "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}, "native_messages_stream": True, "subscription_token_metering": "not supported for Messages", "multiple_text_deltas": len(times) > 1, "wire_delivery_timing": "not independently measured"}


def counter(model):
    expression = 'sum(vllm:request_success_total{namespace="models-as-a-service",model_name="' + model + '"})'
    route = native.get("route", "thanos-querier", "openshift-monitoring")
    host = route.get("spec", {}).get("host")
    need(host and route.get("spec", {}).get("tls"), "Native Thanos verified HTTPS route is absent")
    context = ssl.create_default_context()
    bundle = os.environ.get("RHOAI_STAGE040_CA_BUNDLE")
    if bundle:
        context.load_verify_locations(cafile=bundle)
    token = native.command(["oc", "--request-timeout=" + native.TIMEOUT, "whoami", "-t"]).strip()
    # Thanos includes platform and user-workload metrics; the platform Prometheus
    # local API alone would omit the native LLMI user-workload scrape.
    data = api("https://" + host + "/api/v1/query?" + urlencode({"query": expression}), context, token)
    need(data.get("status") == "success", "Native traffic metric query failed")
    values = data.get("data", {}).get("result", [])
    return sum(float(v["value"][1]) for v in values)


def guarded_persona(path):
    p = Path(path)
    need(p.is_file() and p.stat().st_mode & 0o077 == 0, "Persona kubeconfig must be a private existing login")
    env = dict(os.environ, KUBECONFIG=str(p))
    r = subprocess.run(["/bin/bash", "-c", 'export REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in',
                        "guard", str(native.ROOT)], env=env, capture_output=True, text=True, timeout=30)
    need(r.returncode == 0, "Persona cluster guard failed")
    def oc(*args):
        r = subprocess.run(["oc", "--request-timeout=" + native.TIMEOUT, *args], env=env,
                           capture_output=True, text=True, timeout=30)
        need(r.returncode == 0, "Persona session read failed")
        return r.stdout.strip()
    who = oc("whoami")
    need(who in ("ai-admin", "ai-developer"), "Existing OpenID persona identity is not an approved demo user")
    return who, oc("whoami", "-t")  # Tokens remain in memory only.


def run():
    native.main()  # Direct invocation also qualifies native readiness before key creation.
    persona = os.environ.get("RHOAI_STAGE040_PERSONA_KUBECONFIG")
    if not persona:
        raise Pending("Set RHOAI_STAGE040_PERSONA_KUBECONFIG to an existing private ai-admin or ai-developer login")
    who, user_token = guarded_persona(persona)
    gateway = native.get("gateway", "maas-default-gateway", "openshift-ingress")
    listeners = {l["name"]: l for l in gateway["spec"]["listeners"]}
    base = "https://" + listeners["api"]["hostname"]
    context = ssl.create_default_context()
    bundle = os.environ.get("RHOAI_STAGE040_CA_BUNDLE")
    if bundle:
        context.load_verify_locations(cafile=bundle)  # Public CA material only, never disable verification.
    path = Path(os.environ.get("RHOAI_STAGE040_EVIDENCE_PATH", "/private/tmp/stage040-functional-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8] + ".json"))
    need(path.parent.is_dir() and Path("/private/tmp") in (path.parent.resolve(), *path.parent.resolve().parents) and not path.exists() and not path.is_symlink(), "Use a new private temporary evidence path")
    desired = native.rendered()
    refs = [o for o in desired if o["kind"] == "MaaSModelRef"]
    refs.sort(key=lambda o: (o["metadata"]["namespace"] == "external-models", o["metadata"]["name"]))
    selected_model = os.environ.get("RHOAI_STAGE040_MODEL")
    single_completion = os.environ.get("RHOAI_STAGE040_SINGLE_COMPLETION", "false").lower() == "true"
    if selected_model:
        refs = [ref for ref in refs if ref["metadata"]["name"] == selected_model]
        need(len(refs) == 1, "Selected model must uniquely match a reviewed model reference")
    need(not single_completion or selected_model, "Single-completion qualification requires an explicit model")
    need(1 <= len(refs) <= 5, "Functional model count exceeds reviewed bounded scope")
    subscription = os.environ.get("RHOAI_STAGE040_SUBSCRIPTION", "personal-" + who)
    subscriptions = api(base + "/v1/subscriptions", context, user_token)
    need(isinstance(subscriptions, list) and any(s.get("subscription_id_header") == subscription for s in subscriptions),
         "Persona cannot discover intended subscription")
    evidence = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "persona": who,
                "scope": "bounded authenticated API only; Studio browser and per-request EPP selection remain separate",
                "models": [], "model_http_failures": [], "key_revoked": False,
                "not_qualified": ["quota enforcement", "per-request EPP invocation", "Studio visual acceptance"]}
    evidence["selected_model"] = selected_model
    evidence["single_completion"] = single_completion
    if single_completion:
        evidence["not_qualified"] += ["streaming", "tool calling", "unselected models"]
    key_id = key = None
    revoke_probe = None
    pending_external = False
    failure = None
    try:
        created = api(base + "/v1/api-keys", context, user_token,
                      {"name": "stage040-validation-" + uuid.uuid4().hex[:12], "subscription": subscription,
                       "expiresIn": "1h", "ephemeral": True}, expected=201)
        key_id = created.get("id")
        need(isinstance(key_id, str) and key_id, "Synthetic key identifier absent; expiry limits residual lifecycle risk")
        key = created.get("key")
        need(key and created.get("subscription") == subscription and created.get("ephemeral") is True,
             "Synthetic key contract is incomplete")
        evidence["synthetic_key_id"] = key_id  # Identifier only, never plaintext or prefix.
        # Qualify persona discovery independently of the synthetic inference key.
        catalog = api(base + "/v1/models", context, user_token)
        need(isinstance(catalog.get("data"), list), "Native model catalog response is invalid")
        indexed = {m["id"]: m for m in catalog["data"]}
        for ref in refs:
            name, ns = ref["metadata"]["name"], ref["metadata"]["namespace"]
            external = ns == "external-models"
            if external and os.environ.get("RHOAI_STAGE040_TEST_EXTERNAL", "true").lower() != "true":
                pending_external = True
                continue
            model_id = catalog_id(ref, desired)
            need(model_id in indexed and indexed[model_id].get("ready") is True, "Approved model is missing or not ready in persona catalog")
            endpoint = indexed[model_id].get("url", "")
            expected_host = listeners["api" if external else ("qwen3-6" if name == "qwen3-6-27b" else "qwen3-8")]["hostname"]
            need(urlsplit(endpoint).hostname == expected_host, "Native model discovery selects wrong listener hostname")
            model_inputs = [o for o in desired if o["kind"] == "ExternalModel" and o["metadata"]["namespace"] == ns and o["metadata"]["name"] == name]
            native_messages = external and len(model_inputs) == 1 and model_inputs[0]["spec"]["externalProviderRefs"][0].get("apiFormat") == "messages"
            if native_messages:
                provider_ref = model_inputs[0]["spec"]["externalProviderRefs"][0]
                need(len(model_inputs[0]["spec"]["externalProviderRefs"]) == 1, "Native Messages qualification requires one reviewed provider")
                current_ref = native.get("maasmodelrefs.maas.opendatahub.io", name, ns)
                need(current_ref.get("status", {}).get("endpoint") == endpoint, "Messages catalog URL differs from native controller endpoint")
                current_model = native.get("externalmodels.inference.opendatahub.io", name, ns)
                route = native.get("httproute", current_model["status"]["httpRouteName"], ns)
                parsed = urlsplit(endpoint); url = endpoint.rstrip("/") + ("/messages" if parsed.path.rstrip("/").endswith("/v1") else "/v1/messages")
                request_path = urlsplit(url).path
                matches = [m for rule in route["spec"]["rules"] for m in rule.get("matches", [])]
                prefix_route = any(not m.get("headers") and m.get("path", {}).get("type", "PathPrefix") == "PathPrefix" and m["path"].get("value") not in (None, "/") and request_path.startswith(m["path"]["value"].rstrip("/") + "/") for m in matches)
                body_route = current_ref["status"].get("resolvedModelAlias") == model_id and request_path == provider_ref["path"] and any(m.get("path") == {"type": "PathPrefix", "value": "/"} and any(h.get("name", "").lower() == "x-gateway-model-name" and h.get("type", "Exact") == "Exact" and h.get("value") == model_id for h in m.get("headers", [])) for m in matches)
                need(prefix_route or body_route, "Messages URL/body alias does not match generated native route")
                payload = {"model": model_id, "max_tokens": 32, "stream": True, "messages": [{"role": "user", "content": "Count from 1 to 8, separated by commas."}]}
                for token in (None, "stage040-invalid-" + uuid.uuid4().hex):
                    with request(url, context, token, payload, native_messages=True) as denied:
                        need(denied.status in (401, 403), "Missing/invalid Messages x-api-key did not fail closed")
                revoke_probe = (url, payload, True)
                with request(url, context, key, payload, native_messages=True) as response:
                    if response.status != 200:
                        evidence["model_http_failures"].append({"model": name, "catalog_id": model_id, "phase": "native-messages-stream", "http_status": response.status})
                        raise HTTPFailure(response.status)
                    result = read_messages_sse(response, provider_ref["targetModel"])
                result.update(model=name, catalog_id=model_id, unauthenticated_denied=True, invalid_key_denied=True, bounded_requests=1, routing="native-model-prefix" if prefix_route else "native-body-model", native_route_uid=route["metadata"]["uid"], native_route_generation=route["metadata"]["generation"])
                evidence["not_qualified"] = [x for x in evidence["not_qualified"] if x != "streaming"]
                evidence["models"].append(result)
                continue
            url = completion_url(endpoint)
            payload = {"model": model_id, "messages": [{"role": "user", "content": "Reply with exactly OK."}], "max_tokens": 8}
            if name == "gpt-6-luna":
                payload.pop("max_tokens"); payload.update(max_completion_tokens=32, reasoning_effort="none")
            elif not external:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            with request(url, context, body=payload) as negative:
                need(negative.status in (401, 403), "Unauthenticated inference did not fail closed")
            with request(url, context, "stage040-invalid-" + uuid.uuid4().hex, payload) as invalid:
                need(invalid.status in (401, 403), "Invalid synthetic key did not fail closed")
            if single_completion:
                revoke_probe = (url, payload)
            elif not external and revoke_probe is None:
                revoke_probe = (url, dict(payload, max_tokens=1))
            before = counter(name) if not external else None
            phase = "completion"
            try:
                response = api(url, context, key, payload)
                need(response.get("choices") and response["choices"][0].get("message", {}).get("content") and
                     response.get("usage", {}).get("total_tokens", 0) > 0, "Bounded completion or usage is absent")
                result = {"model": name, "catalog_id": model_id, "unauthenticated_denied": True, "invalid_key_denied": True, "completion_with_usage": True}
                result["usage"] = {field: response["usage"][field] for field in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance(response["usage"].get(field), int)}
                evidence["models"].append(result)  # Preserve successes if a later stream/metric test fails.
                if single_completion:
                    revoke_probe = (url, payload)
                    result["streaming_and_tools_tested"] = False
                    continue
                stream = dict(payload, stream=True, stream_options={"include_usage": True})
                stream["messages"] = [{"role": "user", "content": "Count from 1 to 20, separated by commas. Do not think."}]
                stream["max_completion_tokens" if name == "gpt-6-luna" else "max_tokens"] = 64
                phase = "stream"
                with request(url, context, key, stream) as response:
                    if response.status != 200:
                        raise HTTPFailure(response.status)
                    result.update(read_sse(response))
                if name == "gpt-6-luna":
                    phase = "tool-call"
                    tools = dict(payload, max_completion_tokens=128,
                                 messages=[{"role": "user", "content": "Call report_status with status OK."}],
                                 tools=[{"type": "function", "function": {"name": "report_status", "description": "Return a status", "parameters": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"], "additionalProperties": False}}}],
                                 tool_choice={"type": "function", "function": {"name": "report_status"}})
                    reply = api(url, context, key, tools)
                    calls = reply.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                    need(any(c.get("function", {}).get("name") == "report_status" and json.loads(c["function"]["arguments"]).get("status") == "OK" for c in calls), "Bounded GPT-6 Luna function call failed")
                    result["tool_call"] = True
            except HTTPFailure as error:
                evidence["model_http_failures"].append({"model": name, "catalog_id": model_id,
                                                       "phase": phase, "http_status": error.status})
                failure = RuntimeError("One or more bounded model API checks failed; inspect sanitized per-model evidence")
                print("[FAIL] Bounded " + name + " " + phase + " HTTP status " + str(error.status))
                continue
            if not external:
                deadline = time.monotonic() + 90
                while counter(name) <= before:
                    need(time.monotonic() < deadline, "Local inference traffic counter did not increase")
                    time.sleep(5)
                result["traffic_counter_increased"] = True
                llmi = native.get("llminferenceservices.serving.kserve.io", name, "models-as-a-service")
                router = llmi.get("status", {}).get("router", {}).get("scheduler", {})
                scheduler = llmi.get("status", {}).get("workloads", {}).get("scheduler", {})
                # These are shipped observed topology fields, not proof a request invoked EPP.
                result["native_scheduler"] = {"inference_pool": router.get("inferencePool", {}).get("name"),
                    "epp_service": router.get("service", {}).get("name"),
                    "workload": scheduler.get("name"), "ready_replicas": scheduler.get("readyReplicas")}
                result["per_request_epp_selection"] = "not qualified by this API test"
            print("[PASS] Bounded " + name + " authentication, completion, incremental SSE and usage" + (" with traffic metric" if not external else ""))
    except Exception as error:
        failure = error
    finally:
        if key_id:
            try:
                revoked = api(base + "/v1/api-keys/" + quote(key_id, safe=""), context, user_token, method="DELETE")
                need(revoked.get("id") == key_id and revoked.get("status") == "revoked", "Synthetic key revocation not confirmed")
                evidence["key_revoked"] = True
                if key and revoke_probe:
                    with request(revoke_probe[0], context, key, revoke_probe[1], native_messages=len(revoke_probe) == 3 and revoke_probe[2]) as denied:
                        need(denied.status in (401, 403), "Revoked synthetic key inference was not denied")
                    evidence["revoked_key_inference_denied"] = True
            except Exception:
                failure = RuntimeError("Synthetic key revocation failed; use recorded synthetic key ID for scoped cleanup")
        evidence["passed"] = failure is None and not pending_external
        evidence["external_skipped"] = pending_external
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
            output.write(json.dumps(evidence, indent=2) + "\n")
        print("Sanitized functional evidence saved; no tokens, URLs or response text included")
    if failure:
        raise failure
    if pending_external:
        raise Pending("External inference was explicitly skipped; full API functional acceptance remains pending")
    print("[PASS] Explicit bounded API functional checks and synthetic key revocation. Quota enforcement, Studio visual acceptance and per-request EPP selection remain separately unqualified.")


if __name__ == "__main__":
    try:
        run()
    except Pending as error:
        print("[PENDING] " + str(error)); sys.exit(2)
    except Exception as error:
        print("[FAIL] " + (str(error) if isinstance(error, RuntimeError) else "Bounded functional response could not be qualified")); sys.exit(1)
