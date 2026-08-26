from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import EmbeddingService, get_default_embedding_service, vector_literal
from app.schemas.knowledge import KnowledgeDocumentSource
from scripts.demo_seed.constants import DEMO_BUCKET


DEMO_CHUNKS = [
    (
        "delivery_delay",
        "客户咨询物流延迟时，先表达歉意并确认订单号，说明会核查最新物流节点；如果超过承诺时效，客服可以升级给运营主管处理。",
    ),
    (
        "refund_request",
        "客户申请退款时，先核验商品状态、签收时间和店铺售后政策；需要收集照片、订单号和具体诉求，边界情况升级给运营负责人。",
    ),
    (
        "size_exchange",
        "鞋子尺码偏小需要换大一码时，若客户签收后7天内、商品未穿着、吊牌和包装完整，可以引导客户发起换货并提供订单号和商品照片。",
    ),
    (
        "seven_day_return",
        "7天无理由退货政策：自签收次日起7天内，商品完好（未使用、未洗涤、吊牌完整、包装无破损）可申请无理由退货。以下情况不支持7天无理由退货：贴身衣物、定制商品、生鲜食品、已激活的数字产品。退货流程：客户在订单页发起退货申请 → 客服核验商品状态 → 审核通过后通知客户寄回 → 仓库签收验货 → 3个工作日内退款至原支付账户。",
    ),
    (
        "quality_issue",
        "质量问题处理流程：客户反馈商品存在质量问题时，客服需立即致歉并收集以下信息：订单号、商品照片（含瑕疵细节）、问题描述。15天内质量问题可免费换新或全额退款；15-30天内质量问题提供换新服务；超过30天需转接售后主管评估。快递费由店铺承担，客服需引导客户保留商品等待快递上门取件。质量问题的退换货不受7天无理由退货限制。",
    ),
    (
        "invoice",
        "发票开具规则：支持电子普票和电子专票。普票在下单时可勾选自动开具，专票需在订单完成后3个工作日内申请。开具专票需提供：公司名称、税号、注册地址、注册电话、开户银行、银行账号。发票内容默认为商品明细，可改为办公用品。电子发票在开具后24小时内发送至客户预留邮箱。如需重开发票，需在开票后30天内联系客服处理。",
    ),
    (
        "member_points",
        "会员积分规则：消费1元积1分，签到每日5分，评价商品10分，评价+晒图20分。积分可用于抵扣订单金额（100积分=1元）或兑换优惠券。会员等级：普通会员（0-999分）、银卡（1000-4999分，享95折）、金卡（5000-19999分，享9折+生日礼包）、钻石卡（20000分以上，享85折+专属客服+优先发货）。积分有效期2年，到期未使用自动清零。",
    ),
    (
        "coupon_policy",
        "优惠券使用说明：优惠券分为满减券、折扣券、运费券三种。满减券需订单金额达到门槛才可使用，折扣券直接按比例折扣。每笔订单只能使用一张优惠券，不可叠加。优惠券有效期30天，过期自动作废。使用限制：特价商品、秒杀商品不支持优惠券；跨境订单仅支持满减券。退换货时优惠券不退回。领取优惠券后需在7天内使用，否则系统自动回收。",
    ),
    (
        "shipping_policy",
        "配送范围与时效：全国包邮（西藏、新疆、青海需补差价20元）。默认发中通快递，客户可加急选顺丰（补差价15元）。发货时效：工作日16:00前付款当日发货，16:00后次日发货；周末及法定节假日延后至下一个工作日发货。配送时效：一线城市2-3天，二三线城市3-5天，偏远地区5-7天。大件商品（家具、家电）由专业物流配送，时效7-10天，需预约送货时间。",
    ),
]


async def seed_knowledge(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
) -> tuple[KnowledgeBase, KnowledgeDocument]:
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.name == "Customer Service SOP",
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if not knowledge_base:
        knowledge_base = KnowledgeBase(
            tenant_id=tenant_id,
            name="Customer Service SOP",
            description="Demo knowledge base for ecommerce customer service responses.",
            visibility="department",
            department_ids=[str(department_id)],
            rag_engine="pgvector",
            embedding_model_key=settings.rag_embedding_model_key,
            retrieval_config={"top_k": 5, "score_threshold": 0.55},
            status="active",
            document_count=1,
            tags=["demo", "customer_service"],
            metadata_json={"demo_seed": True},
        )
        session.add(knowledge_base)
        await session.flush()

    document = await _get_or_create_document(session, tenant_id=tenant_id, knowledge_base=knowledge_base)
    await _ensure_demo_chunks(
        session,
        tenant_id=tenant_id,
        knowledge_base=knowledge_base,
        document=document,
    )
    return knowledge_base, document


async def _get_or_create_document(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    knowledge_base: KnowledgeBase,
) -> KnowledgeDocument:
    result = await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.filename == "customer-service-sop.md",
            KnowledgeDocument.deleted_at.is_(None),
        )
    )
    document = result.scalar_one_or_none()
    if document:
        if document.source not in {item.value for item in KnowledgeDocumentSource}:
            document.source = KnowledgeDocumentSource.INTERNAL_IMPORT.value
        document.chunk_count = len(DEMO_CHUNKS)
        return document
    document = KnowledgeDocument(
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base.id,
        filename="customer-service-sop.md",
        content_type="text/markdown",
        size_bytes=2048,
        checksum_sha256="demo_customer_service_sop",
        source=KnowledgeDocumentSource.INTERNAL_IMPORT.value,
        status="indexed",
        storage_bucket=DEMO_BUCKET,
        storage_object_key="demo/customer-service-sop.md",
        rag_document_id="demo-rag-doc-customer-service-sop",
        chunk_count=len(DEMO_CHUNKS),
        metadata_json={"demo_seed": True},
    )
    session.add(document)
    await session.flush()
    return document


async def _ensure_demo_chunks(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
) -> None:
    embedding_service = get_default_embedding_service()
    existing_result = await session.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeChunk.knowledge_base_id == knowledge_base.id,
            KnowledgeChunk.document_id == document.id,
        )
    )
    by_index = {chunk.chunk_index: chunk for chunk in existing_result.scalars().all()}
    for index, (section, chunk_text) in enumerate(DEMO_CHUNKS):
        chunk = by_index.get(index)
        if chunk is None:
            chunk = KnowledgeChunk(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base.id,
                document_id=document.id,
                chunk_index=index,
                text=chunk_text,
                search_text=_normalize_search_text(chunk_text),
                token_count=max(1, len(chunk_text) // 4),
                source_name=document.filename,
                metadata_json={"demo_seed": True, "section": section},
            )
            session.add(chunk)
            await session.flush()
        else:
            chunk.text = chunk_text
            chunk.search_text = _normalize_search_text(chunk_text)
            chunk.token_count = max(1, len(chunk_text) // 4)
            chunk.source_name = document.filename
            chunk.metadata_json = {"demo_seed": True, "section": section}
        await _write_demo_embedding(session, chunk, chunk_text, embedding_service)

    for index, chunk in by_index.items():
        if index >= len(DEMO_CHUNKS):
            await session.delete(chunk)

    document.chunk_count = len(DEMO_CHUNKS)
    knowledge_base.document_count = 1
    await session.flush()


async def _write_demo_embedding(
    session: AsyncSession,
    chunk: KnowledgeChunk,
    chunk_text: str,
    embedding_service: EmbeddingService,
) -> None:
    embedding = embedding_service.embed_text(chunk_text)
    await session.execute(
        text(
            """
            UPDATE knowledge_chunks
            SET embedding_model_key = :embedding_model_key,
                embedding_dimensions = :embedding_dimensions,
                embedding = CAST(:embedding AS vector),
                updated_at = NOW()
            WHERE id = :chunk_id
            """
        ),
        {
            "chunk_id": chunk.id,
            "embedding_model_key": embedding.model_key,
            "embedding_dimensions": embedding.dimensions,
            "embedding": vector_literal(embedding.vector),
        },
    )


def _normalize_search_text(value: str) -> str:
    return " ".join(value.lower().split())
