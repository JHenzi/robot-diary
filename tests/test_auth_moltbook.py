"""Tests for Moltbook 'Sign in with Moltbook' auth module."""
import pytest
from unittest.mock import patch, MagicMock

from src.auth.moltbook import (
    MoltbookAuthError,
    get_identity_token_from_headers,
    get_verified_agent_from_headers,
    verify_identity,
)


class TestGetIdentityTokenFromHeaders:
    def test_extracts_token_when_present(self):
        headers = {"X-Moltbook-Identity": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        assert get_identity_token_from_headers(headers) == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

    def test_case_insensitive(self):
        headers = {"x-moltbook-identity": "token123"}
        assert get_identity_token_from_headers(headers) == "token123"

    def test_returns_none_when_missing(self):
        assert get_identity_token_from_headers({}) is None
        assert get_identity_token_from_headers({"Authorization": "Bearer x"}) is None

    def test_strips_whitespace(self):
        headers = {"X-Moltbook-Identity": "  token  "}
        assert get_identity_token_from_headers(headers) == "token"

    def test_empty_value_returns_none(self):
        headers = {"X-Moltbook-Identity": ""}
        assert get_identity_token_from_headers(headers) is None


class TestVerifyIdentity:
    @pytest.fixture
    def mock_response(self):
        return {
            "success": True,
            "valid": True,
            "agent": {
                "id": "uuid-123",
                "name": "TestBot",
                "karma": 100,
                "avatar_url": "https://example.com/avatar.png",
                "is_claimed": True,
                "owner": {"x_handle": "human", "x_verified": True},
            },
        }

    def test_success_returns_agent(self, mock_response):
        with patch("src.auth.moltbook.requests.post") as post:
            post.return_value.json.return_value = mock_response
            post.return_value.raise_for_status = MagicMock()
            agent = verify_identity("token123", app_key="moltdev_test")
        assert agent["id"] == "uuid-123"
        assert agent["name"] == "TestBot"
        assert agent["karma"] == 100
        post.assert_called_once()
        call_kw = post.call_args[1]
        assert call_kw["headers"]["X-Moltbook-App-Key"] == "moltdev_test"
        assert call_kw["json"] == {"token": "token123"}

    def test_success_with_audience(self, mock_response):
        with patch("src.auth.moltbook.requests.post") as post:
            post.return_value.json.return_value = mock_response
            post.return_value.raise_for_status = MagicMock()
            verify_identity("token", audience="myapp.com", app_key="key")
        assert post.call_args[1]["json"] == {"token": "token", "audience": "myapp.com"}

    def test_empty_token_raises(self):
        with pytest.raises(MoltbookAuthError) as exc_info:
            verify_identity("", app_key="key")
        assert exc_info.value.code == "missing_token"
        assert exc_info.value.status_code == 401

    def test_invalid_token_raises_with_code(self):
        with patch("src.auth.moltbook.requests.post") as post:
            post.return_value.json.return_value = {"valid": False, "error": "invalid_token"}
            with pytest.raises(MoltbookAuthError) as exc_info:
                verify_identity("bad", app_key="key")
        assert exc_info.value.code == "invalid_token"
        assert exc_info.value.status_code == 401

    def test_expired_token_raises(self):
        with patch("src.auth.moltbook.requests.post") as post:
            post.return_value.json.return_value = {
                "valid": False,
                "error": "identity_token_expired",
                "hint": "Get a new token",
            }
            with pytest.raises(MoltbookAuthError) as exc_info:
                verify_identity("expired", app_key="key")
        assert exc_info.value.code == "identity_token_expired"
        assert exc_info.value.status_code == 401
        assert exc_info.value.hint == "Get a new token"

    def test_invalid_app_key_raises(self):
        with patch("src.auth.moltbook.requests.post") as post:
            post.return_value.json.return_value = {"valid": False, "error": "invalid_app_key"}
            with pytest.raises(MoltbookAuthError) as exc_info:
                verify_identity("token", app_key="wrong")
        assert exc_info.value.code == "invalid_app_key"
        assert exc_info.value.status_code == 401

    def test_no_app_key_raises_when_key_not_passed(self):
        with patch("src.auth.moltbook.get_app_key", return_value=None):
            with pytest.raises(MoltbookAuthError) as exc_info:
                verify_identity("token")
        assert exc_info.value.code == "missing_app_key"
        assert exc_info.value.status_code == 500


class TestGetVerifiedAgentFromHeaders:
    def test_success(self):
        with patch("src.auth.moltbook.verify_identity") as verify:
            verify.return_value = {"id": "a1", "name": "Bot"}
            headers = {"X-Moltbook-Identity": "token"}
            agent = get_verified_agent_from_headers(headers)
        assert agent["name"] == "Bot"
        verify.assert_called_once_with("token", audience=None)

    def test_missing_header_raises(self):
        with pytest.raises(MoltbookAuthError) as exc_info:
            get_verified_agent_from_headers({})
        assert exc_info.value.code == "missing_token"
        assert exc_info.value.status_code == 401
