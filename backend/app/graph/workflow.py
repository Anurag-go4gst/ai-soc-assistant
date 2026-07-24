from app.graph.state import InvestigationState


def build_workflow() -> None:
    """Investigation placeholder workflow; live /chat uses the RP hierarchy graph."""
    return None


def run_placeholder_workflow(state: InvestigationState) -> InvestigationState:
    state.route = state.route or "placeholder"
    return state


__all__ = ["build_workflow", "run_placeholder_workflow"]
