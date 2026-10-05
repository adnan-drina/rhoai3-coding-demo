"""Deterministic Stage 080 planner library (M1 evidence → M2 admission).

Importable modules only. CLIs live in the owning skills' ``scripts/``.

Digest order (acyclic; SAD §6):

    evidence-bundle → worklist → admission-receipt
    → admission-receipt

No module here invokes an LLM. Every authoritative output is a canonical
JSON document whose digest is a pure function of its inputs.
"""
