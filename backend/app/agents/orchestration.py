from enum import StrEnum


class AgentOrchestrationRuntime(StrEnum):
    LANGGRAPH = "langgraph"
    LANGCHAIN = "langchain"
    DEEPAGENTS = "deepagents"
    MEDIA_GATEWAY = "media_gateway"
    NATIVE = "native"


LANGGRAPH_STANDARD_FEATURES = [
    "state_graph",
    "typed_state",
    "checkpoint_ready",
    "tool_routing",
    "human_handoff_ready",
]


LANGCHAIN_STANDARD_FEATURES = [
    "prompt_template",
    "runnable_chain",
    "structured_output",
    "tool_binding",
]


MEDIA_GATEWAY_STANDARD_FEATURES = [
    "media_generation_plan",
    "reference_assets",
    "async_job_ready",
    "minio_output_contract",
]
