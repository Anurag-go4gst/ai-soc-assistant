from app.graph.chat_workflow import run_chat_via_langgraph
from app.graph.state import InvestigationState


def build_workflow() -> None:
    """Live /chat LangGraph is built in ``chat_workflow`` (P1 parity)."""
    return None


def run_placeholder_workflow(state: InvestigationState) -> InvestigationState:
    state.route = state.route or "placeholder"
    return state


__all__ = ["build_workflow", "run_placeholder_workflow", "run_chat_via_langgraph"]
