from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.llm import LLMMessageRequest


def render_chat_prompt_messages(
    *,
    system_prompt: str,
    user_prompt: str,
    variables: dict[str, Any] | None = None,
) -> list[LLMMessageRequest]:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
    )
    messages = prompt.format_messages(**(variables or {}))
    return [_message_to_request(message) for message in messages]


def _message_to_request(message: BaseMessage) -> LLMMessageRequest:
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = str(getattr(message, "type", "user") or "user")

    content = message.content
    if isinstance(content, str):
        text = content
    else:
        text = str(content)
    return LLMMessageRequest(role=role, content=text)
