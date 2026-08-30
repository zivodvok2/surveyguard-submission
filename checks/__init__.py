"""QC checks used by the API, CLI, and agentic workflow."""

from .deterministic import run_deterministic_checks

__all__ = ["run_deterministic_checks"]
