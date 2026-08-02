
from dhybrid.agent.messages import MessageStore
from dhybrid.llm.base import ChatMessage, Usage


def test_message_to_api_tool_call():
    m = ChatMessage(
        role="assistant",
        content="",
        tool_calls=[{"id": "t1", "name": "grep", "arguments": {"q": "x"}}],
    )
    api = m.to_api()
    assert '"q": "x"' in api["tool_calls"][0]["function"]["arguments"]


def test_usage_total():
    assert Usage(prompt_tokens=10, completion_tokens=5).total == 15


def test_message_store_append_and_last():
    s = MessageStore()
    s.add("user", "halo")
    s.add_tool_result("t1", "ok")
    assert s.last().role == "tool"
    assert s.last("user").content == "halo"
