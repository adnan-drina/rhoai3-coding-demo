#!/usr/bin/env python3
"""Offline ownership/lifecycle regression tests; no cluster or model calls."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit, parse_qs
import uuid

loader = importlib.util.spec_from_file_location("studio_api", Path(__file__).with_name("studio-api.py"))
studio = importlib.util.module_from_spec(loader)
loader.loader.exec_module(studio)
FOREIGN = str(uuid.UUID(int=900))


class NativeStore:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.objects = {FOREIGN: {"metadata": {"name": FOREIGN}, "spec": {"displayName": "Governed code review", "userData": "preserve"}}}
        self.original = copy.deepcopy(self.objects)
        self.records = {}
        self.posts = 0
        self.reads = {}
        self.deletes = []
        self.calls = []

    def record(self, identifier):
        return copy.deepcopy(self.records[identifier])

    def request(self, method, url, body=None):
        self.calls.append((method, url))
        parsed = urlsplit(url)
        namespace = parse_qs(parsed.query)["namespace"][0]
        if namespace != "demo-sandbox":
            raise studio.NativeError(403)
        if parsed.path.endswith("maas/models"):
            assert method == "GET"
            return {"data": [{"id": "model", "url": "https://model.invalid/v1", "ready": True}]}
        identifier = parsed.path.rsplit("/", 1)[-1]
        if identifier == "agent-profiles":
            if method == "GET":
                return {"data": {"profiles": [{"profileId": key} for key in self.objects]}}
            assert method == "POST"
            self.posts += 1
            if self.mode == "second-create-fails" and self.posts == 2:
                raise studio.NativeError(500)
            if self.mode == "foreign-create-id":
                return {"data": {"profileId": FOREIGN}}
            identifier = str(uuid.UUID(int=self.posts))
            self.objects[identifier] = {"metadata": {"name": identifier}, "spec": copy.deepcopy(body["spec"])}
            self.records[identifier] = {"uid": "uid-" + identifier, "resource_version": "1", "data_hash": "initial"}
            return {"data": {"profileId": identifier}}
        if identifier not in self.objects:
            raise studio.NativeError(404)
        if method == "GET":
            count = self.reads[identifier] = self.reads.get(identifier, 0) + 1
            if self.mode == "first-read-fails" and self.posts == 1 and count == 1:
                raise studio.NativeError(500)
            if count == 2 and identifier != FOREIGN:
                if self.mode == "content-changed":
                    self.objects[identifier]["spec"]["temperature"] = 0.75
                if self.mode in ("uid-changed", "rv-changed", "data-changed"):
                    key = {"uid-changed": "uid", "rv-changed": "resource_version", "data-changed": "data_hash"}[self.mode]
                    self.records[identifier][key] = "changed"
            return {"data": copy.deepcopy(self.objects[identifier])}
        assert method == "DELETE"
        self.deletes.append(identifier)
        if self.mode not in ("delete-not-absent", "delete404-still-present"):
            del self.objects[identifier]
        if self.mode.startswith("delete404"):
            raise studio.NativeError(404)
        return {}


class FixtureLifecycle(unittest.TestCase):
    def run_case(self, mode, succeeds):
        store = NativeStore(mode)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            if succeeds:
                studio.qualify_agents(store.request, "model", store.record)
            else:
                with self.assertRaises((RuntimeError, studio.NativeError)):
                    studio.qualify_agents(store.request, "model", store.record)
        receipt = json.loads(output.getvalue())
        self.assertEqual(store.objects[FOREIGN], store.original[FOREIGN])
        self.assertNotIn(FOREIGN, store.deletes)
        self.assertFalse(any("completion" in urlsplit(url).path or "/prompts" in urlsplit(url).path for _, url in store.calls))
        return store, receipt

    def test_success_removes_only_new_variants(self):
        store, receipt = self.run_case("normal", True)
        self.assertEqual(set(store.objects), {FOREIGN})
        self.assertEqual(len(receipt["cleanup"]["deleted_ids"]), 2)
        self.assertEqual(receipt["cleanup"]["retained"], [])
        self.assertTrue(all(item["persisted"] for item in receipt["profiles"]))

    def test_partial_creation_failure_cleans_first_fixture(self):
        store, receipt = self.run_case("second-create-fails", False)
        self.assertEqual(set(store.objects), {FOREIGN})
        self.assertEqual(len(receipt["cleanup"]["deleted_ids"]), 1)

    def test_failure_after_create_still_cleans(self):
        store, receipt = self.run_case("first-read-fails", False)
        self.assertEqual(set(store.objects), {FOREIGN})
        self.assertEqual(len(receipt["cleanup"]["deleted_ids"]), 1)

    def test_changed_content_or_identity_is_retained(self):
        for mode in ("content-changed", "uid-changed", "rv-changed", "data-changed"):
            with self.subTest(mode=mode):
                store, receipt = self.run_case(mode, False)
                self.assertEqual(store.deletes, [])
                self.assertEqual(len(receipt["cleanup"]["retained"]), 2)
                self.assertEqual(receipt["cleanup"]["deleted_ids"], [])

    def test_foreign_create_id_is_never_adopted(self):
        store, receipt = self.run_case("foreign-create-id", False)
        self.assertEqual(store.deletes, [])
        self.assertEqual(set(store.objects), {FOREIGN})
        self.assertEqual(receipt["cleanup"]["deleted_ids"], [])

    def test_successful_delete_must_prove_absence(self):
        store, receipt = self.run_case("delete-not-absent", False)
        self.assertEqual(len(receipt["cleanup"]["retained"]), 2)
        self.assertEqual(receipt["cleanup"]["deleted_ids"], [])

    def test_delete404_still_requires_read_absence(self):
        store, receipt = self.run_case("delete404-still-present", False)
        self.assertEqual(len(receipt["cleanup"]["retained"]), 2)
        self.assertEqual(receipt["cleanup"]["deleted_ids"], [])
        store, receipt = self.run_case("delete404-absent", True)
        self.assertEqual(set(store.objects), {FOREIGN})
        self.assertEqual(len(receipt["cleanup"]["deleted_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
