"""Claude backend behind the Groq-style `client.chat.completions.create(...)` surface.

GroqClient builds OpenAI-format messages and tool schemas throughout. Rather than
rewrite every call site, this adapter translates those requests to the Anthropic
Messages API and returns objects shaped like Groq's responses
(`response.choices[0].message.content / .tool_calls`, `finish_reason`).
"""
import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)

# Server-side refusal fallback (routes a declined request to another model in the same call)
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_FINISH_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "refusal": "content_filter",
}


def _convert_tools(tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _convert_user_content(content: Any) -> Any:
    """OpenAI user content (str or parts with image_url data URLs) -> Anthropic blocks."""
    if isinstance(content, str) or content is None:
        return content or ""
    blocks = []
    for part in content:
        if part.get("type") == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            url = part["image_url"]["url"]
            if url.startswith("data:"):
                header, data = url.split(",", 1)
                media_type = header[5:].split(";")[0] or "image/jpeg"
                source = {"type": "base64", "media_type": media_type, "data": data}
            else:
                source = {"type": "url", "url": url}
            # Images first reads best for Claude; keep them ahead of the text
            blocks.insert(0, {"type": "image", "source": source})
    return blocks


class _Completions:
    def __init__(self, owner: "ClaudeChatAdapter"):
        self._owner = owner

    def create(self, model: str, messages: List[Dict], tools=None, max_tokens: int = 4096, **_ignored):
        return self._owner._create(model, messages, tools, max_tokens)


class ClaudeChatAdapter:
    """Drop-in for the subset of the Groq client that GroqClient uses."""

    def __init__(self, api_key: str, effort_by_model: Optional[Dict[str, str]] = None):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._effort = effort_by_model or {}
        # Raw assistant content (thinking blocks included) keyed by what GroqClient echoes
        # back, so tool loops replay thinking unchanged instead of a lossy reconstruction.
        self._raw_by_tool_id: Dict[str, list] = {}
        self._raw_by_text: Dict[str, list] = {}
        self.chat = SimpleNamespace(completions=_Completions(self))

    # -- request translation -------------------------------------------------
    def _convert_messages(self, messages: List[Dict]):
        system_parts: List[str] = []
        out: List[Dict] = []
        pending_results: List[Dict] = []

        def flush_results():
            if pending_results:
                out.append({"role": "user", "content": list(pending_results)})
                pending_results.clear()

        for m in messages:
            role = m.get("role")
            if role == "system":
                if not out:
                    system_parts.append(m.get("content") or "")
                else:
                    flush_results()
                    out.append({"role": "user", "content": m.get("content") or ""})
                continue
            if role == "tool":
                pending_results.append({
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": str(m.get("content") or ""),
                })
                continue
            flush_results()
            if role == "assistant":
                out.append({"role": "assistant", "content": self._assistant_content(m)})
            else:
                out.append({"role": "user", "content": _convert_user_content(m.get("content"))})
        flush_results()
        return "\n\n".join(p for p in system_parts if p), out

    def _assistant_content(self, m: Dict):
        tool_calls = m.get("tool_calls") or []
        if tool_calls and tool_calls[0].get("id") in self._raw_by_tool_id:
            return self._raw_by_tool_id[tool_calls[0]["id"]]
        text = m.get("content") or ""
        if not tool_calls and text in self._raw_by_text:
            return self._raw_by_text[text]
        blocks = [{"type": "text", "text": text}] if text else []
        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": args})
        return blocks or [{"type": "text", "text": "(no output)"}]

    # -- call ----------------------------------------------------------------
    def _create(self, model: str, messages: List[Dict], tools, max_tokens: int):
        system, converted = self._convert_messages(messages)
        effort = self._effort.get(model, "medium")
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": converted,
            # Adaptive thinking spends from max_tokens; keep the caller's budget for visible text
            "max_tokens": int(max_tokens) + 8000,
            "output_config": {"effort": effort},
        }
        if system:
            kwargs["system"] = system
        claude_tools = _convert_tools(tools)
        if claude_tools:
            # GroqClient keeps only the final reply's text, so prose written alongside a
            # tool call would be lost from the entry
            kwargs["system"] = (system + "\n\n" if system else "") + (
                "If you use a tool, call it before you start writing. Your final reply must "
                "contain the complete text, from its first word to its last."
            )
            kwargs["tools"] = claude_tools
            kwargs["tool_choice"] = {"type": "auto"}
        if model.startswith(("claude-sonnet-5-5", "claude-opus-5")):
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"

        with self._client.beta.messages.stream(**kwargs) as stream:
            resp = stream.get_final_message()

        if resp.stop_reason == "refusal":
            category = getattr(getattr(resp, "stop_details", None), "category", None)
            logger.warning(f"Claude declined the request (category: {category})")

        raw = [b.model_dump(exclude_none=True) for b in resp.content if b.type != "fallback"]
        text = "".join(b.text for b in resp.content if b.type == "text")
        tool_calls = [
            SimpleNamespace(
                id=b.id,
                type="function",
                function=SimpleNamespace(name=b.name, arguments=json.dumps(b.input)),
            )
            for b in resp.content if b.type == "tool_use"
        ]
        if tool_calls:
            self._raw_by_tool_id[tool_calls[0].id] = raw
        elif text:
            self._raw_by_text[text] = raw

        message = SimpleNamespace(content=text or None, tool_calls=tool_calls or None, role="assistant")
        choice = SimpleNamespace(message=message, finish_reason=_FINISH_REASONS.get(resp.stop_reason, "stop"))
        return SimpleNamespace(choices=[choice], model=resp.model, usage=resp.usage)
