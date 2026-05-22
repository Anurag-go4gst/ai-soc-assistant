def record_node(trace_id: str, node_name: str, status: str) -> dict[str, str]:
    return {"trace_id": trace_id, "node_name": node_name, "status": status}
