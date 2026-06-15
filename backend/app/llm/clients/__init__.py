"""Real HTTP clients for configured LLM endpoints (live-chat synthesis only).

These are deliberately separate from `app/connectors/llm`, whose
`get_llm_connector()` keys off the legacy `llm_mode` setting and returns a mock.
The clients here are gated by the governed `AI_SOC_LLM_*` config and are only
ever called from the live `/chat` synthesis path, never the Experience Center
fixture path.
"""

from app.llm.clients.endpoint_resolver import build_synthesis_client_from_settings
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import (
    ChatResult,
    LocalChatClient,
    LocalChatError,
)

__all__ = [
    "ChatResult",
    "FailoverChatClient",
    "LocalChatClient",
    "LocalChatError",
    "build_synthesis_client_from_settings",
]
