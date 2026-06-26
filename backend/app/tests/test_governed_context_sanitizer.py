from __future__ import annotations

from app.llm.governed_context_package import GovernedContextPackage


def test_to_prompt_block_redacts_bearer_tokens() -> None:
    package = GovernedContextPackage(
        raw_query="check bearer sk-testtoken1234567890abcdef",
        soc_kb_snippets=["Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"],
    )
    block = package.to_prompt_block()
    assert "Bearer [redacted]" in block or "[redacted]" in block
    assert "eyJhbGciOiJIUzI1NiJ9" not in block
