"""Compile the qualification pipeline to Kubernetes-native manifests ("Working with AI pipelines", 1.2.2).

The pipeline server stores pipeline definitions in Kubernetes, so GitOps applies the Pipeline and PipelineVersion
custom resources this writes. Requires Python 3.11+ and kfp 2.14.3 or later; use kfp 2.16.1 (with
kfp-kubernetes 2.16.1): every step installs the compiling SDK version, and the RHOAI runtime image's package index
offers 2.16.1. A changed pipeline gets a new version name.

Usage: python compile.py <version>     e.g. python compile.py v1
"""
import pathlib
import sys

from kfp import compiler
from kfp.compiler.compiler_utils import KubernetesManifestOptions

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pipeline import qualification  # noqa: E402

version = sys.argv[1]
out = (pathlib.Path(__file__).resolve().parents[3] / "gitops/stages/050-model-evaluation/model-qualification"
       / "pipeline/agentic-coding-model-qualification.yaml")
out.parent.mkdir(parents=True, exist_ok=True)
compiler.Compiler().compile(
    pipeline_func=qualification,
    package_path=str(out),
    kubernetes_manifest_format=True,
    kubernetes_manifest_options=KubernetesManifestOptions(
        pipeline_name="agentic-coding-model-qualification",
        pipeline_display_name="Agentic coding model qualification",
        pipeline_version_name=f"agentic-coding-model-qualification-{version}",
        pipeline_version_display_name=f"agentic-coding-model-qualification {version}",
        namespace="evaluated-models",
        include_pipeline_manifest=True,
    ),
)
print(f"compiled {version} -> {out}")
