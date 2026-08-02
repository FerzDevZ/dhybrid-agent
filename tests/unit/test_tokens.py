from dhybrid.llm.base import ChatMessage
from dhybrid.llm.tokens import estimate_messages, estimate_tokens


def test_estimate_nonzero_and_monotonic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("x" * 1000) > estimate_tokens("x" * 10)


def test_estimate_messages_counts():
    msgs = [ChatMessage(role="user", content="a" * 100)] * 3
    assert estimate_messages(msgs) >= 3 * 25
