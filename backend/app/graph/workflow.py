from app.graph.state import InvestigationState


def build_workflow() -> None:
    """Placeholder for future LangGraph workflow construction."""
    return None


def run_placeholder_workflow(state: InvestigationState) -> InvestigationState:
    state.route = state.route or "placeholder"
    return state
