"""Workstream D (P4) — governed prompt/role policy architecture.

This package is generic prompt-policy architecture. It owns no SPL semantics: the
live SPL producer/compiler seam belongs to workstream B (P2), and the trace oracle
belongs to workstream A (P1). Nothing here executes an LLM, calls MCP, or grants
authority; it describes and constrains prompts deterministically.
"""
