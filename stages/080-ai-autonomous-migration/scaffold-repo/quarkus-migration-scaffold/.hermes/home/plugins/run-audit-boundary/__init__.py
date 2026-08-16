"""Hermes loads this directory as a package; register lives in plugin.py."""
from .plugin import register

__all__ = ["register"]
