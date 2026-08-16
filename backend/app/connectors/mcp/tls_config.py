"""TLS + secret-reference helpers for the existing Splunk MCP transport.

No new client. httpx and urllib both consume these values so Settings verify
and live search share one policy. Defaults stay verify-on.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

from app.config import settings


def mcp_tls_verify(*, tls_verify: bool | None = None, ca_cert_path: str | None = None) -> bool | str:
    """httpx ``verify=`` value: True, False, or a CA file path."""
    verify = settings.splunk_mcp_tls_verify if tls_verify is None else bool(tls_verify)
    if not verify:
        return False
    path = (settings.splunk_mcp_ca_cert_path if ca_cert_path is None else ca_cert_path) or ""
    cleaned = str(path).strip()
    return cleaned if cleaned else True


def urllib_ssl_context(*, tls_verify: bool | None = None, ca_cert_path: str | None = None) -> ssl.SSLContext | None:
    """``urlopen`` context. None means the stdlib default (verify on)."""
    verify = mcp_tls_verify(tls_verify=tls_verify, ca_cert_path=ca_cert_path)
    if verify is False:
        return ssl._create_unverified_context()
    if isinstance(verify, str):
        return ssl.create_default_context(cafile=verify)
    return None


def resolve_splunk_mcp_token() -> str:
    """Bearer token from env/settings or an externally supplied file reference."""
    token = (settings.splunk_mcp_token or "").strip()
    if token:
        return token
    env_token = os.environ.get("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "").strip()
    if env_token:
        return env_token
    for raw in (
        settings.splunk_mcp_token_file,
        os.environ.get("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN_FILE", ""),
        os.environ.get("SPLUNK_MCP_TOKEN_FILE", ""),
    ):
        path = str(raw or "").strip()
        if not path:
            continue
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def token_reference_configured() -> bool:
    """True when a secret is supplied without echoing it."""
    if (settings.splunk_mcp_token or "").strip():
        return True
    if os.environ.get("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "").strip():
        return True
    for raw in (
        settings.splunk_mcp_token_file,
        os.environ.get("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN_FILE", ""),
        os.environ.get("SPLUNK_MCP_TOKEN_FILE", ""),
    ):
        path = str(raw or "").strip()
        if path and Path(path).is_file():
            return True
    return False
