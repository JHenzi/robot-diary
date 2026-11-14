"""ClaudeChatAdapter translates GroqClient's OpenAI-format requests to the Messages API."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.llm.claude_adapter import ClaudeChatAdapter


def _block(**kw):
    b = SimpleNamespace(**kw)
    b.model_dump = lambda exclude_none=True: dict(kw)
    return b


def _adapter(final):
    a = ClaudeChatAdapter(api_key="test_key_123456", effort_by_model={"m": "low"})
    stream = MagicMock()
    stream.__enter__.return_value.get_final_message.return_value = final
    a._client = MagicMock()
    a._client.beta.messages.stream.return_value = stream
    return a


def test_tool_loop_round_trip_replays_raw_blocks():
    thinking = _block(type="thinking", thinking="", signature="sig")
    tool = _block(type="tool_use", id="tu_1", name="query_memories", input={"query": "van"})
    a = _adapter(SimpleNamespace(content=[thinking, tool], stop_reason="tool_use", model="m", usage=None))

    r = a.chat.completions.create(
        model="m",
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "query_memories", "description": "d", "parameters": {"type": "object", "properties": {}}}}],
        temperature=0.7, max_tokens=500,
    )
    msg = r.choices[0].message
    assert r.choices[0].finish_reason == "tool_calls"
    assert json.loads(msg.tool_calls[0].function.arguments) == {"query": "van"}
    kwargs = a._client.beta.messages.stream.call_args.kwargs
    assert kwargs["system"] == "sys" and "temperature" not in kwargs
    assert kwargs["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert kwargs["output_config"] == {"effort": "low"}

    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "tu_1", "type": "function", "function": {"name": "query_memories", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "tu_1", "content": "result"},
    ]
    _, converted = a._convert_messages(history)
    assert converted[1]["content"][0]["type"] == "thinking"  # replayed unchanged
    assert converted[2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "result"}]}


def test_image_data_url_becomes_base64_block_and_length_maps():
    a = _adapter(SimpleNamespace(content=[_block(type="text", text="a street")], stop_reason="max_tokens", model="m", usage=None))
    r = a.chat.completions.create(model="m", messages=[{"role": "user", "content": [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
    ]}])
    assert r.choices[0].message.content == "a street"
    assert r.choices[0].finish_reason == "length"
    content = a._client.beta.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert content[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
