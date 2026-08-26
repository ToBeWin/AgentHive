from app.core.config import settings


def llm_mock_allowed() -> bool:
    """LLM mock responses are only allowed for local development demos."""
    return settings.environment.lower() == "development"


def llm_mock_disabled_message(adapter_name: str) -> str:
    return (
        f"{adapter_name} mock mode is disabled outside development. "
        "Configure live endpoint credentials before using this provider."
    )
