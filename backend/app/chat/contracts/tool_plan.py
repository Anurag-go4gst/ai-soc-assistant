from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


ToolPhase = Literal["pre_answer", "pre_mcp", "post_mcp"]


class ToolPlanItem(BaseModel):
    tool: str
    phase: ToolPhase
    required: bool


class ToolPlan(BaseModel):
    tools: list[ToolPlanItem]
    mcp_execution_allowed: bool
