"""Create a business operations knowledge base for the report_writer agent.

Seeds weekly operations data (sales, users, products, customer service) so
report_writer can ground its reports in real data instead of fabricating.
Run inside the backend container:

    docker exec agenthive-dev-backend python -m scripts.demo_seed.business_knowledge
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import text
from sqlmodel import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.agent_module import AgentInstance
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import EmbeddingService, get_default_embedding_service, vector_literal
from app.schemas.knowledge import KnowledgeDocumentSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


BUSINESS_CHUNKS = [
    (
        "weekly_sales_gmv",
        "2026年第27周（6月30日-7月5日）销售数据汇总：周GMV 428.6万元，环比增长12.3%。订单总量18,452单，日均2,636单。客单价232元，环比下降3.2%。"
        "渠道分布：APP端65%、小程序22%、PC端8%、第三方平台5%。支付方式：微信支付48%、支付宝35%、银行卡12%、其他5%。"
        "TOP3品类：女装156万元（占比36%）、鞋靴89万元（21%）、配饰62万元（14%）。退货率8.7%，环比下降1.2个百分点。",
    ),
    (
        "weekly_user_growth",
        "2026年第27周用户增长数据：新增注册用户3,847人，环比增长18.6%。周活跃用户（WAU）52,340人，日活跃用户均值7,890人。"
        "新用户转化率24.3%（注册→首单），老用户复购率31.2%。会员等级分布：普通会员68%、银卡21%、金卡9%、钻石卡2%。"
        "获客渠道：自然流量42%、付费广告28%、社交分享18%、老客推荐12%。获客成本（CAC）38元/人，环比下降15%。"
        "用户留存：7日留存48%、14日留存35%、30日留存22%。",
    ),
    (
        "weekly_product_performance",
        "2026年第27周商品运营数据：在售SKU 4,820个，动销率62.4%。TOP5热销商品：1.夏季棉麻连衣裙（1,243件/28.7万元）；"
        "2.运动透气跑鞋（982双/22.1万元）；3.防晒冰丝外套（876件/19.4万元）；4.真皮通勤单鞋（654双/15.8万元）；"
        "5.丝光棉T恤（1,102件/12.6万元）。库存预警SKU 87个（库存<30天），超期库存SKU 23个（>180天）。"
        "本周上新SKU 42个，下架SKU 18个。缺货导致的订单流失约156单，预估损失GMV 3.6万元。",
    ),
    (
        "weekly_customer_service",
        "2026年第27周客服与售后数据：咨询总量4,723次，日均674次。首次响应平均时长28秒，解决率92.4%。"
        "工单分类：物流咨询32%、退换货28%、商品咨询18%、售后投诉12%、发票10%。投诉工单56件，环比下降22%。"
        "客诉率1.2%（投诉单/总订单），满意度评分4.6/5.0。退款金额38.7万元（占GMV 9%），退款原因：质量问题42%、"
        "尺寸不符28%、不喜欢18%、物流问题12%。平均退款处理时长1.8个工作日。7天无理由退货占比65%，质量问题退货占比23%。",
    ),
    (
        "weekly_logistics_fulfillment",
        "2026年第27周物流履约数据：发货订单18,452单，准时发货率97.8%。平均发货时长6.2小时（付款→出库）。"
        "物流时效：一线城市平均2.1天、二三线城市3.4天、偏远地区5.8天。物流投诉37件（占咨询量0.8%），"
        "主要问题：配送延迟18件、快递丢失5件、包装破损14件。大件商品（家具/家电）配送14单，预约成功率100%。"
        "加急顺丰订单342单（占总单量1.9%），补差价收入5,130元。仓库盘点差异率0.03%，在可控范围内。",
    ),
    (
        "weekly_marketing_campaigns",
        "2026年第27周营销活动数据：1.夏季清仓大促（6/28-7/4）：GMV 186万元，订单7,820单，ROI 4.2。"
        "满300减50券核销4,210张，折扣券核销2,860张。活动期间UV 28.4万，转化率2.75%。"
        "2.老客专属日（7/2）：复购订单1,240单，GMV 32.6万元，复购率环比提升8%。"
        "3.新人礼包：领取2,840份，核销率41%。优惠券整体核销率23.6%，环比下降2个百分点。"
        "下周计划：7/7启动会员日预热，7/9-7/11金卡/钻石卡专享3倍积分+专属折扣。",
    ),
    (
        "weekly_risks_issues",
        "2026年第27周风险与问题：1.供应链风险：夏季棉麻连衣裙面料供应商交期延迟3天，影响下周上新计划（已启动备选供应商）。"
        "2.库存风险：防晒品类库存仅剩12天，若持续高温将面临断货（已紧急补单2,000件）。"
        "3.客诉风险：运动跑鞋鞋底开胶投诉集中（12件），已联系供应商排查批次（涉及SKU: RS-2024-018）。"
        "4.系统风险：7/3晚支付通道短暂中断18分钟，影响约230单（已全部补偿优惠券）。"
        "5.合规风险：跨境订单发票开具流程需优化，财务反馈3笔专票超期（已处理）。"
        "需决策事项：a)棉麻连衣裙上新是否推迟至7/12？b)运动跑鞋是否主动召回RS-2024-018批次？",
    ),
]


async def seed_business_knowledge() -> None:
    async with AsyncSessionLocal() as session:
        # Find demo tenant + department
        row = (
            await session.execute(
                text(
                    "SELECT t.id, d.id FROM tenants t "
                    "LEFT JOIN departments d ON d.tenant_id = t.id "
                    "WHERE t.slug = 'demo' ORDER BY d.created_at LIMIT 1"
                )
            )
        ).first()
        if not row:
            logger.error("Demo tenant not found. Run demo seed first.")
            return
        tenant_id = UUID(str(row[0]))
        department_id = UUID(str(row[1])) if row[1] else None

        # Check if business KB already exists
        result = await session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.name == "Business Operations Weekly Data",
                KnowledgeBase.deleted_at.is_(None),
            )
        )
        knowledge_base = result.scalar_one_or_none()

        if not knowledge_base:
            knowledge_base = KnowledgeBase(
                tenant_id=tenant_id,
                name="Business Operations Weekly Data",
                description="业务运营周报数据知识库（销售/用户/商品/客服/物流/营销/风险），供报告生成助手使用。",
                visibility="tenant",
                department_ids=[str(department_id)] if department_id else [],
                rag_engine="pgvector",
                embedding_model_key=settings.rag_embedding_model_key,
                retrieval_config={"top_k": 5, "score_threshold": 0.45},
                status="active",
                document_count=1,
                tags=["demo", "business", "report_writer"],
                metadata_json={"demo_seed": True, "purpose": "report_writer_data_source"},
            )
            session.add(knowledge_base)
            await session.flush()
            logger.info("Created knowledge base: %s", knowledge_base.id)
        else:
            logger.info("Knowledge base already exists: %s", knowledge_base.id)

        # Get or create document
        doc_result = await session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.knowledge_base_id == knowledge_base.id,
                KnowledgeDocument.filename == "business-operations-w27-2026.md",
                KnowledgeDocument.deleted_at.is_(None),
            )
        )
        document = doc_result.scalar_one_or_none()
        if not document:
            document = KnowledgeDocument(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base.id,
                filename="business-operations-w27-2026.md",
                content_type="text/markdown",
                size_bytes=8192,
                checksum_sha256="demo_business_ops_w27_2026",
                source=KnowledgeDocumentSource.INTERNAL_IMPORT.value,
                status="indexed",
                storage_bucket="demo-bucket",
                storage_object_key="demo/business-ops-w27-2026.md",
                rag_document_id="demo-rag-doc-business-ops-w27",
                chunk_count=len(BUSINESS_CHUNKS),
                metadata_json={"demo_seed": True, "week": "2026-W27"},
            )
            session.add(document)
            await session.flush()
        else:
            document.chunk_count = len(BUSINESS_CHUNKS)

        # Write chunks with BGE-M3 embeddings
        embedding_service = get_default_embedding_service()
        existing = await session.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeChunk.knowledge_base_id == knowledge_base.id,
                KnowledgeChunk.document_id == document.id,
            )
        )
        by_index = {c.chunk_index: c for c in existing.scalars().all()}

        for index, (section, chunk_text) in enumerate(BUSINESS_CHUNKS):
            chunk = by_index.get(index)
            search_text = " ".join(chunk_text.lower().split())
            if chunk is None:
                chunk = KnowledgeChunk(
                    tenant_id=tenant_id,
                    knowledge_base_id=knowledge_base.id,
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk_text,
                    search_text=search_text,
                    token_count=max(1, len(chunk_text) // 4),
                    source_name=document.filename,
                    metadata_json={"demo_seed": True, "section": section, "week": "2026-W27"},
                )
                session.add(chunk)
                await session.flush()
            else:
                chunk.text = chunk_text
                chunk.search_text = search_text
                chunk.token_count = max(1, len(chunk_text) // 4)
                chunk.source_name = document.filename
                chunk.metadata_json = {"demo_seed": True, "section": section, "week": "2026-W27"}

            embedding = embedding_service.embed_text(chunk_text)
            await session.execute(
                text(
                    """
                    UPDATE knowledge_chunks
                    SET embedding_model_key = :model_key,
                        embedding_dimensions = :dimensions,
                        embedding = CAST(:embedding AS vector),
                        updated_at = NOW()
                    WHERE id = :chunk_id
                    """
                ),
                {
                    "chunk_id": chunk.id,
                    "model_key": embedding.model_key,
                    "dimensions": embedding.dimensions,
                    "embedding": vector_literal(embedding.vector),
                },
            )

        # Remove surplus chunks
        for index, chunk in by_index.items():
            if index >= len(BUSINESS_CHUNKS):
                await session.delete(chunk)

        document.chunk_count = len(BUSINESS_CHUNKS)
        knowledge_base.document_count = 1

        # Bind to report_writer agent instance
        instance_result = await session.execute(
            select(AgentInstance).where(
                AgentInstance.tenant_id == tenant_id,
                AgentInstance.agent_key == "report_writer",
                AgentInstance.status == "active",
            )
        )
        instance = instance_result.scalar_one_or_none()
        if instance:
            config = dict(instance.config or {})
            existing_ids = config.get("knowledge_base_ids", [])
            kb_id_str = str(knowledge_base.id)
            if kb_id_str not in existing_ids:
                config["knowledge_base_ids"] = (existing_ids or []) + [kb_id_str]
                config["knowledge_top_k"] = 5
                instance.config = config
                logger.info("Bound KB %s to report_writer instance %s", knowledge_base.id, instance.id)
            else:
                logger.info("report_writer already bound to KB %s", knowledge_base.id)
        else:
            logger.warning("report_writer agent instance not found")

        await session.commit()
        logger.info("Done. KB: %s, chunks: %d", knowledge_base.id, len(BUSINESS_CHUNKS))


if __name__ == "__main__":
    asyncio.run(seed_business_knowledge())
