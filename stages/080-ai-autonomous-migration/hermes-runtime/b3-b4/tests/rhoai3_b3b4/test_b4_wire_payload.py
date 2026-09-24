"""B4: the Qwen3.8 non-thinking profile must be what goes on the wire.

Real pinned client path: ``hermes chat -q ... -Q`` (subprocess) with the
config rendered from the Stage 050 producer, provider ``qwen38``
(custom provider, api_mode chat_completions), against a loopback fake that
records the exact JSON request body. No real model.
"""

import json
import os

import pytest

from . import _harness as H
from .fake_openai_server import FakeProvider

CAPTURE = os.environ.get("RHOAI3_B4_CAPTURE")  # optional path: write captured bodies here


def _capture(label, bodies):
    if CAPTURE:
        with open(CAPTURE, "a") as fh:
            for b in bodies:
                fh.write(json.dumps({"case": label, "body": H.wire_fields(b)}, sort_keys=True) + "\n")


def test_wire_payload_matches_nonthinking_profile(monkeypatch):
    with FakeProvider([("text", "hello")]) as provider:
        H.clean_env(monkeypatch, provider)
        H.write_home(H.worker_config(), profile=None)
        proc = H.run_cli_query("say hi")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        reqs = H.agent_requests(provider)
        assert len(reqs) == 1
        body = reqs[0]
        _capture("main_agent_request", [body])
        assert H.profile_mismatches(body) == []
        assert body["model"] == H.MODEL_ID
        assert body["max_tokens"] == H.OUTPUT_CAP
        assert body["stream"] is True
        # Nothing else sets sampling: every sampling key on the wire is a declared one.
        sampling = {"temperature", "top_p", "top_k", "min_p", "presence_penalty",
                    "repetition_penalty", "frequency_penalty", "seed"}
        assert {k for k in body if k in sampling} == set(H.NONTHINKING_ROW) - {"chat_template_kwargs"}


def test_profile_check_detects_dropped_extra_body(monkeypatch):
    """Control: the same assertion fails when extra_body is not configured."""
    cfg = H.worker_config()
    del cfg["providers"]["qwen38"]["extra_body"]
    with FakeProvider([("text", "hello")]) as provider:
        H.clean_env(monkeypatch, provider)
        H.write_home(cfg, profile=None)
        proc = H.run_cli_query("say hi")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        body = H.agent_requests(provider)[0]
        _capture("control_extra_body_dropped", [body])
        missing = H.profile_mismatches(body)
        assert "chat_template_kwargs: missing" in missing
        assert "presence_penalty: missing" in missing


def test_extra_body_wins_over_top_level_sampling():
    """Precedence at the pinned SDK (openai 2.24.0): extra_body is shallow-merged
    over the JSON body, so an extra_body key replaces a same-named top-level key."""
    import openai

    with FakeProvider([("text", "x")]) as provider:
        client = openai.OpenAI(base_url=provider.base_url, api_key="sk-fake", max_retries=0)
        client.chat.completions.create(
            model=H.MODEL_ID, messages=[{"role": "user", "content": "hi"}],
            temperature=0.1, top_p=0.5, extra_body=dict(H.NONTHINKING_ROW),
        )
        body = provider.chat_requests()[0]
        _capture("sdk_precedence_top_level_0.1_vs_extra_body_0.7", [body])
        assert body["temperature"] == 0.7 and body["top_p"] == 0.8


def _aux_compression_bodies(monkeypatch, cfg):
    """Issue the compressor's two real auxiliary calls from the worker agent."""
    script = (
        "import json\n"
        "from cli import HermesCLI\n"
        "from agent.auxiliary_client import call_llm\n"
        "cli = HermesCLI()\n"
        "assert cli._ensure_runtime_credentials()\n"
        "r = cli._resolve_turn_agent_config('hi')\n"
        "assert cli._init_agent(model_override=r['model'], runtime_override=r['runtime'],"
        " request_overrides=r.get('request_overrides'))\n"
        "cc = cli.agent.context_compressor\n"
        "rt = {'model': cc.model, 'provider': cc.provider, 'base_url': cc.base_url,"
        " 'api_key': cc.api_key, 'api_mode': cc.api_mode}\n"
        # context_compressor.py summary call (no max_tokens) and micro-summary call
        "call_llm(task='compression', main_runtime=rt, messages=[{'role': 'user', 'content': 's'}])\n"
        "call_llm(task='compression', main_runtime=rt, messages=[{'role': 'user', 'content': 'm'}],"
        " max_tokens=1500, temperature=0.1)\n"
    )
    import subprocess
    import sys
    with FakeProvider([("text", "summary")]) as provider:
        H.clean_env(monkeypatch, provider)
        home = H.write_home(cfg, profile=None)
        proc = subprocess.run([sys.executable, "-c", script], env=dict(os.environ),
                              cwd=str(home), capture_output=True, text=True, timeout=180)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return provider.chat_requests()


def test_auxiliary_compression_request_matches_profile_producer_config(monkeypatch):
    """Producer config: auxiliary.compression.extra_body is the profile's
    request_body plus max_tokens = quota.max_output_tokens (32768). Both
    compressor calls (summary and micro-summary) carry the row and the output
    bound on the wire; the micro-summary's top-level temperature 0.1 is
    overridden by extra_body."""
    bodies = _aux_compression_bodies(monkeypatch, H.worker_config())
    _capture("aux_compression_producer_config", bodies)
    assert len(bodies) == 2
    for body in bodies:
        assert H.profile_mismatches(body) == []
        assert body["max_tokens"] == H.AUX_OUTPUT_CAP
    assert bodies[1]["temperature"] == 0.7


def test_every_auto_auxiliary_slot_carries_the_profile():
    """Config-level: every auxiliary slot that is not disabled and runs on the
    main model (provider auto) declares the profile's request body plus the
    per-request output bound."""
    aux = H.worker_config()["auxiliary"]
    live = {name: slot for name, slot in aux.items()
            if isinstance(slot, dict) and slot.get("enabled", True) is not False}
    assert set(live) == {"compression"}
    for name, slot in live.items():
        assert slot.get("provider", "auto") == "auto"
        assert slot.get("extra_body") == {**H.NONTHINKING_ROW, "max_tokens": H.AUX_OUTPUT_CAP}, name
