# Architecture

AI SOC Assistant is organized around a future LangGraph control plane that coordinates alert triage, evidence retrieval, safeguard checks, and analyst-facing responses.

## Control Plane

LangGraph will own investigation state transitions, node execution, recovery paths, and trace emission. The current scaffold only defines placeholder state and workflow interfaces.

## Splunk MCP Read Path

Splunk MCP will be reached through a backend MCP client after deterministic SPL validation and approval checks. The current MCP client is a placeholder and performs no real execution.

Stage 3H separates core Splunk MCP read/search tools from optional Splunk AI Assistant (`saia_*`) advisory tools. SAIA outputs can help produce candidate SPL, explanations, or optimization hints, but they are not execution evidence and cannot bypass deterministic validation or MCP execution gates.

## RAG and GraphRAG Layer

The knowledge vault stores SOPs, runbooks, SPL templates, MITRE notes, assets, detections, and scenario packs. Later phases can add vector retrieval, keyword retrieval, and graph context retrieval.

## LLM Reasoning Layer

Foundation-Sec LLM endpoints will be introduced later as a reasoning layer. The LLM must receive only minimized evidence and context, never credentials or raw logs.

## Deterministic Safeguards

Safeguards validate SPL, output claims, evidence provenance, prompt injection risk, and data minimization before tool execution and before analyst output.

## Routing Maturity Model

Routing starts with simple mock planner and deterministic route comparison. Later phases can add policy validation, calibrated confidence, adjudication, and traceable route override workflows.
