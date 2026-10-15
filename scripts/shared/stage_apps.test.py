"""Offline tests for the shared stage deploy primitives in stage_apps.py (no cluster)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_apps

SHA = "1" * 40
REPO = "https://source.example/demo.git"


def application(name, revision=SHA, path=None, phase="Succeeded", sync="Synced", health="Healthy", automated=True):
    path = path or stage_apps.components("070")[[a["metadata"]["name"] for a in stage_apps.components("070")].index(name)]["spec"]["source"]["path"]
    policy = {"syncOptions": ["RespectIgnoreDifferences=true", "ClientSideApplyMigration=false"]}
    if automated:
        policy["automated"] = {"prune": True, "selfHeal": True}
    return {"metadata": {"name": name},
            "spec": {"project": "rhoai-demo", "destination": dict(stage_apps.DESTINATION), "syncPolicy": policy,
                     "source": {"repoURL": REPO, "targetRevision": revision, "path": path}},
            "status": {"sync": {"status": sync, "revision": revision}, "health": {"status": health},
                       "operationState": {"phase": phase, "syncResult": {"revision": revision, "source": {"path": path}}}}}


class DeployGroups(unittest.TestCase):
    def test_sequential_stage_deploys_one_order_group_at_a_time(self):
        groups = stage_apps.deploy_groups(stage_apps.stamped("070", SHA, REPO))
        self.assertEqual([[a["metadata"]["name"] for a in g] for g in groups][:2], [["070-namespaces"], ["070-identity"]])
        self.assertEqual(groups[-1][0]["metadata"]["name"], "070-rhdh")

    def test_a_sequential_stage_cannot_skip_waiting(self):
        with self.assertRaisesRegex(RuntimeError, "sequentially"):
            stage_apps.deploy("070", SHA, REPO, wait=False)

    def test_other_stages_deploy_all_components_together(self):
        self.assertEqual(len(stage_apps.deploy_groups(stage_apps.stamped("050", SHA, REPO))), 1)


class Stamped(unittest.TestCase):
    def test_cluster_patches_go_to_the_named_component_only(self):
        patch_ = [{"target": {"kind": "Gateway"}, "patch": "[]"}]
        apps = {a["metadata"]["name"]: a for a in stage_apps.stamped("040", SHA, REPO, patches={"040-gateway-governance": patch_})}
        self.assertEqual(apps["040-gateway-governance"]["spec"]["source"]["kustomize"]["patches"], patch_)
        self.assertNotIn("kustomize", apps["040-model-access"]["spec"]["source"])
        with self.assertRaisesRegex(RuntimeError, "unknown components"):
            stage_apps.stamped("040", SHA, REPO, patches={"040-gateway": patch_})


class SyncOperation(unittest.TestCase):
    def test_carries_own_sync_options_and_automated_prune(self):
        op = stage_apps.sync_operation(application("070-gitlab"), "test")["operation"]["sync"]
        self.assertEqual(op["revision"], SHA)
        self.assertIn("RespectIgnoreDifferences=true", op["syncOptions"])
        self.assertTrue(op["prune"])
        self.assertNotIn("prune", stage_apps.sync_operation(application("070-gitlab", automated=False), "test")["operation"]["sync"])

    def test_a_successful_sync_of_the_current_source_needs_no_new_sync(self):
        self.assertTrue(stage_apps.synced_this_source(application("070-gitlab")))
        moved = application("070-gitlab"); moved["spec"]["source"]["targetRevision"] = "2" * 40
        self.assertFalse(stage_apps.synced_this_source(moved))


class Wait(unittest.TestCase):
    def test_waits_for_delayed_reconciliation_then_returns(self):
        now = [0]
        pending = application("070-gitlab", health="Progressing")
        states = iter([pending, pending, application("070-gitlab")])
        stage_apps.wait_for("070", ["070-gitlab"], SHA, REPO, 60, reader=lambda name: next(states),
                            clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
        self.assertEqual(now[0], 20)

    def test_a_failed_operation_at_this_revision_is_terminal(self):
        with self.assertRaisesRegex(RuntimeError, "failed"):
            stage_apps.wait_for("070", ["070-gitlab"], SHA, REPO, 60, reader=lambda n: application(n, phase="Failed"))

    def test_an_earlier_revision_failure_is_not_terminal_but_times_out(self):
        old = application("070-gitlab", phase="Failed"); old["status"]["operationState"]["syncResult"]["revision"] = "2" * 40
        now = [0]
        with self.assertRaisesRegex(RuntimeError, "not reconciled in time"):
            stage_apps.wait_for("070", ["070-gitlab"], SHA, REPO, 15, reader=lambda n: old,
                                clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))

    def test_a_component_on_another_path_or_repository_is_not_reconciled(self):
        for field, value in (("path", "gitops/elsewhere"), ("repoURL", "https://foreign.example/x.git")):
            app = application("070-gitlab"); app["spec"]["source"][field] = value
            now = [0]
            with self.assertRaises(RuntimeError):
                stage_apps.wait_for("070", ["070-gitlab"], SHA, REPO, 5, reader=lambda n: app,
                                    clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))


class StageProblems(unittest.TestCase):
    def test_script_deployed_components_keep_their_own_revision(self):
        apps = {a["metadata"]["name"]: a for a in stage_apps.components("010", separate=True)}
        def live(name):
            app = application("070-gitlab", revision=("2" * 40 if ORDER_FREE(apps[name]) else SHA), path=apps[name]["spec"]["source"]["path"])
            app["metadata"]["name"] = name
            app["spec"]["destination"] = apps[name]["spec"]["destination"]
            return app
        ORDER_FREE = lambda a: stage_apps.ORDER not in a["metadata"].get("annotations", {})
        with patch.object(stage_apps, "get_application", side_effect=live):
            self.assertEqual(stage_apps.stage_problems("010", SHA, REPO, separate=True), [])
            self.assertTrue(stage_apps.stage_problems("010", "3" * 40, REPO, separate=True))


class FlatApplications(unittest.TestCase):
    def test_file_name_must_equal_application_name(self):
        app = ("apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: 070-demo\n  labels: {demo.rhoai.io/stage: '070'}\n"
               "  annotations: {demo.rhoai.io/deploy-order: '1'}\nspec: {source: {path: gitops/stages/070-demo/070-demo}}\n")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "gitops/applications").mkdir(parents=True)
            (root / "gitops/applications/070-demo.yaml").write_text(app)
            self.assertEqual(stage_apps.names("070", root), ["070-demo"])
            (root / "gitops/applications/070-demo.yaml").rename(root / "gitops/applications/070-renamed.yaml")
            stage_apps._components.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "named after its Application"):
                stage_apps.names("070", root)


class SelectRevision(unittest.TestCase):
    def test_refuses_edited_untracked_and_unpublished_stage_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root, remote = Path(temp) / "repo", Path(temp) / "remote.git"
            def git(*a):
                return subprocess.check_output(["git", "-C", str(root), *a], stderr=subprocess.DEVNULL, text=True).strip()
            (root / "gitops/stages/070-demo").mkdir(parents=True); (root / "gitops/applications").mkdir(parents=True)
            source = root / "stages/070-demo/deploy.sh"; source.parent.mkdir(parents=True); source.write_text("initial")
            git("init"); git("config", "user.name", "Fixture"); git("config", "user.email", "fixture@example.invalid")
            (root / "gitops/stages/070-demo/.keep").write_text("")
            app = root / "gitops/applications/070-demo-component.yaml"; app.write_text("initial")
            other = root / "gitops/applications/040-other.yaml"; other.write_text("initial")
            git("add", "."); git("commit", "-m", "fixture"); sha = git("rev-parse", "HEAD")
            subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, check=True); git("push", str(remote), "HEAD:main")
            env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "url." + remote.as_uri() + ".insteadOf", "GIT_CONFIG_VALUE_0": REPO}
            with patch.dict(os.environ, env):
                self.assertEqual(stage_apps.select_revision("070", "HEAD", REPO, root), sha)
                source.write_text("edited")
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    stage_apps.select_revision("070", "HEAD", REPO, root)
                source.write_text("initial")
                # The stage's flat Application files are stage source; another stage's are not.
                app.write_text("edited")
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    stage_apps.select_revision("070", "HEAD", REPO, root)
                app.write_text("initial"); other.write_text("edited")
                self.assertEqual(stage_apps.select_revision("070", "HEAD", REPO, root), sha)
                other.write_text("initial"); (source.parent / "extra").write_text("new")
                with self.assertRaisesRegex(RuntimeError, "Untracked"):
                    stage_apps.select_revision("070", "HEAD", REPO, root)
                git("add", "."); git("commit", "-m", "unpublished")
                with self.assertRaisesRegex(RuntimeError, "not advertised"):
                    stage_apps.select_revision("070", "HEAD", REPO, root)


if __name__ == "__main__":
    unittest.main()
