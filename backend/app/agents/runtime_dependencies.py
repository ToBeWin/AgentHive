from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class AgentRuntimeDependency:
    package: str
    import_name: str
    required_for: list[str]


REQUIRED_AGENT_RUNTIME_DEPENDENCIES = [
    AgentRuntimeDependency(
        package="langchain-core",
        import_name="langchain_core",
        required_for=["langchain", "langgraph"],
    ),
    AgentRuntimeDependency(
        package="langchain",
        import_name="langchain",
        required_for=["langchain"],
    ),
    AgentRuntimeDependency(
        package="langgraph",
        import_name="langgraph",
        required_for=["langgraph"],
    ),
]


def agent_runtime_dependency_status() -> dict[str, object]:
    dependencies = []
    missing = []
    for dependency in REQUIRED_AGENT_RUNTIME_DEPENDENCIES:
        available = find_spec(dependency.import_name) is not None
        row = {
            "package": dependency.package,
            "import_name": dependency.import_name,
            "available": available,
            "required_for": dependency.required_for,
        }
        dependencies.append(row)
        if not available:
            missing.append(dependency.package)

    return {
        "status": "healthy" if not missing else "unhealthy",
        "message": (
            "Agent orchestration dependencies are installed."
            if not missing
            else f"Missing Agent orchestration dependencies: {', '.join(missing)}."
        ),
        "details": {
            "dependencies": dependencies,
            "missing": missing,
        },
    }
