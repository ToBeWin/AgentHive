from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.media.schemas import MediaGenerationKind
from app.services.agent_module_service import ensure_agent_module_runnable_for_tenant


MEDIA_GENERATION_MODULE_KEYS = {
    MediaGenerationKind.IMAGE.value: "agent.image_generation",
    MediaGenerationKind.VIDEO.value: "agent.video_generation",
}


def media_generation_module_key(kind: MediaGenerationKind | str) -> str:
    kind_value = kind.value if isinstance(kind, MediaGenerationKind) else kind
    return MEDIA_GENERATION_MODULE_KEYS[kind_value]


async def ensure_media_generation_module_runnable(
    session: AsyncSession,
    principal: Principal,
    kind: MediaGenerationKind | str,
) -> str:
    module_key = media_generation_module_key(kind)
    await ensure_agent_module_runnable_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        module_key=module_key,
        usage_label="media generation",
    )
    return module_key
