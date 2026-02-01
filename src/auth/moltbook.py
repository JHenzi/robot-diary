"""
Moltbook "Sign in with Moltbook" authentication.

Verifies agent identity tokens via the Moltbook API and attaches the verified
agent to the request context for use in route handlers.

Usage:
  - Extract token: token = get_identity_token_from_headers(request.headers)
  - Verify and get agent: agent = verify_identity(token)
  - Or use the FastAPI dependency: Depends(require_moltbook_agent) and access request.state.moltbook_agent
"""
import os
import logging
from typing import Any, Mapping, Optional

import requests

logger = logging.getLogger(__name__)

MOLTBOOK_VERIFY_URL = "https://moltbook.com/api/v1/agents/verify-identity"
IDENTITY_HEADER = "X-Moltbook-Identity"
APP_KEY_HEADER = "X-Moltbook-App-Key"

# Error code -> HTTP status (from Moltbook docs)
ERROR_STATUS = {
    "identity_token_expired": 401,
    "invalid_token": 401,
    "invalid_app_key": 401,
    "missing_app_key": 401,
    "agent_not_found": 404,
    "agent_deactivated": 403,
    "audience_required": 401,
    "audience_mismatch": 401,
    "rate_limit_exceeded": 429,
}


class MoltbookAuthError(Exception):
    """Raised when Moltbook identity verification fails."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: int = 401,
        hint: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.hint = hint


def get_app_key() -> Optional[str]:
    """Return the Moltbook app API key from config or environment."""
    try:
        from .. import config as app_config
        key = getattr(app_config, "MOLTBOOK_APP_KEY", None)
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("MOLTBOOK_APP_KEY", "").strip() or None


def get_identity_token_from_headers(headers: Mapping[str, str]) -> Optional[str]:
    """
    Extract the X-Moltbook-Identity token from request headers.

    Header lookup is case-insensitive. Returns None if the header is missing or empty.
    """
    if not headers:
        return None
    # Support both dict and dict-like (e.g. werkzeug Headers)
    for k, v in headers.items():
        if k.lower() == IDENTITY_HEADER.lower():
            return (v or "").strip() or None
    return None


def verify_identity(
    token: str,
    audience: Optional[str] = None,
    app_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Verify an identity token with Moltbook and return the verified agent profile.

    Args:
        token: The identity token from the X-Moltbook-Identity header.
        audience: Optional audience restriction (must match token audience if token was issued with one).
        app_key: Optional app API key; if not provided, uses MOLTBOOK_APP_KEY from config/env.

    Returns:
        The verified agent dict (id, name, karma, avatar_url, is_claimed, owner, etc.).

    Raises:
        MoltbookAuthError: If the token is missing, invalid, expired, or verification fails.
    """
    if not (token or "").strip():
        raise MoltbookAuthError(
            "No identity token provided",
            code="missing_token",
            status_code=401,
        )

    key = app_key or get_app_key()
    if not key:
        raise MoltbookAuthError(
            "Moltbook app API key not configured (set MOLTBOOK_APP_KEY)",
            code="missing_app_key",
            status_code=500,
        )

    body: dict[str, Any] = {"token": token.strip()}
    if audience is not None:
        body["audience"] = audience

    try:
        resp = requests.post(
            MOLTBOOK_VERIFY_URL,
            headers={
                "Content-Type": "application/json",
                APP_KEY_HEADER: key,
            },
            json=body,
            timeout=10,
        )
    except requests.RequestException as e:
        logger.warning("Moltbook verify request failed: %s", e)
        raise MoltbookAuthError(
            "Failed to verify identity",
            code="verify_error",
            status_code=502,
        ) from e

    try:
        data = resp.json()
    except ValueError:
        raise MoltbookAuthError(
            "Invalid response from identity provider",
            code="invalid_response",
            status_code=502,
        )

    if data.get("valid") is True and data.get("agent"):
        return data["agent"]

    error_code = data.get("error", "invalid_token")
    hint = data.get("hint")
    status_code = ERROR_STATUS.get(error_code, 401)
    raise MoltbookAuthError(
        message=error_code.replace("_", " ").title(),
        code=error_code,
        status_code=status_code,
        hint=hint,
    )


def get_verified_agent_from_headers(
    headers: Mapping[str, str],
    audience: Optional[str] = None,
) -> dict[str, Any]:
    """
    Extract X-Moltbook-Identity from headers, verify with Moltbook, and return the agent.

    Convenience helper for use in route handlers. Attach the result to your request
    context (e.g. request.state.moltbook_agent = agent).

    Raises:
        MoltbookAuthError: If header is missing or token is invalid/expired.
    """
    token = get_identity_token_from_headers(headers)
    if not token:
        raise MoltbookAuthError(
            "No identity token provided (X-Moltbook-Identity header required)",
            code="missing_token",
            status_code=401,
        )
    return verify_identity(token, audience=audience)


def require_moltbook_agent(request: Any) -> dict[str, Any]:
    """
    FastAPI dependency: require X-Moltbook-Identity, verify with Moltbook, attach agent to request.

    Use as: Depends(require_moltbook_agent). The verified agent is set on request.state.moltbook_agent
    and also returned. Raises HTTPException 401/403/404/429 on invalid or expired tokens.

    Requires FastAPI to be installed. Pass a FastAPI Request (injected by Depends).
    """
    try:
        from fastapi import HTTPException
    except ImportError as err:
        raise RuntimeError("FastAPI is required for require_moltbook_agent dependency") from err

    token = get_identity_token_from_headers(request.headers)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_token", "message": "X-Moltbook-Identity header required"},
        )
    try:
        agent = verify_identity(token)
    except MoltbookAuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "hint": e.hint},
        ) from e
    request.state.moltbook_agent = agent
    return agent
