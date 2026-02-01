"""Moltbook 'Sign in with Moltbook' authentication for AI agent identity verification."""

from .moltbook import (
    MoltbookAuthError,
    get_app_key,
    get_identity_token_from_headers,
    get_verified_agent_from_headers,
    require_moltbook_agent,
    verify_identity,
)

__all__ = [
    "MoltbookAuthError",
    "get_app_key",
    "get_identity_token_from_headers",
    "get_verified_agent_from_headers",
    "require_moltbook_agent",
    "verify_identity",
]
