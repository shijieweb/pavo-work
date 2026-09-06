"""数据库会话管理。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """获取数据库会话。"""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """初始化数据库（创建所有表 + 插入默认提示词模板）。"""
    from app.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 插入默认提示词模板
    await _seed_prompt_templates()


async def _seed_prompt_templates() -> None:
    """插入默认提示词模板。"""
    from sqlalchemy import select
    from app.models.prompt import PromptTemplate
    
    templates = [
        {
            "name": "project_description_optimize",
            "purpose": "优化项目描述，使其更专业、结构化",
            "content": """你是一位资深产品经理。请帮助用户优化项目描述，使其更专业、结构化。

【项目基本信息】
名称：{project_name}
当前描述：{current_description}

【优化要求】
1. 保持原意，提升表达清晰度
2. 使用结构化格式（目标用户、核心功能、关键场景）
3. 语言简洁专业，避免空泛描述
4. 输出JSON格式：{"description": "...", "target_users": [...], "core_functions": [...], "key_scenarios": [...]}
5. 目标用户不超过5个，核心功能不超过8个，关键场景不超过5个

【示例输出】
{"description": "面向中小团队的敏捷协作工具，支持需求管理、任务追踪和文档协同", "target_users": ["产品经理", "开发负责人", "设计师"], "core_functions": ["需求看板", "任务分配", "文档协作"], "key_scenarios": ["每日站会", "迭代规划", "需求评审"]}""",
        },
        {
            "name": "project_generate_description",
            "purpose": "根据用户输入优化项目简介",
            "content": """你是一位资深产品经理。请帮助用户优化项目简介，使其更专业、结构化、清晰。

【输入信息】
项目名称：{project_name}
用户草稿：{user_input}

【优化要求】
1. 保留用户原意，提升表达质量
2. 补充缺失的关键信息（目标用户、核心功能、使用场景）
3. 语言简洁专业，避免空洞词汇（如"赋能"、"抓手"、"闭环"）
4. 输出JSON格式：{{"description": "...", "target_users": [...], "core_functions": [...], "key_scenarios": [...]}}
5. description: 1-2句话的项目定位说明
6. target_users: 目标用户列表（不超过5个）
7. core_functions: 核心功能列表（不超过8个）
8. key_scenarios: 关键使用场景（不超过5个）

【示例】
输入：电商平台，支持多商户入驻
输出：{{"description": "面向中小商家的B2B2C电商平台，支持多商户入驻、商品管理、订单履约和资金结算全流程", "target_users": ["商家入驻方", "平台运营", "消费者"], "core_functions": ["商户入驻审核", "商品管理", "订单处理", "支付结算", "数据分析"], "key_scenarios": ["商家入驻流程", "商品上架管理", "用户下单购买", "平台运营管理"]}}""",
        },
        {
            "name": "story_expansion",
            "purpose": "扩展用户故事",
            "content": "根据用户输入，生成详细的用户故事格式：作为[角色]，我希望[功能]，以便[价值]。输出JSON数组格式。"
        },
        {
            "name": "dev_doc_generate",
            "purpose": "生成开发文档",
            "content": "根据项目信息，生成API文档、数据模型和接口说明。输出结构化的Markdown文档。"
        },
        {
            "name": "test_doc_generate",
            "purpose": "生成测试文档",
            "content": "根据功能描述，生成测试用例。包含前置条件、测试步骤、预期结果。"
        },
        {
            "name": "acceptance_doc_generate",
            "purpose": "生成验收文档",
            "content": "根据功能需求，生成验收标准文档。使用Given/When/Then格式。"
        },
        {
            "name": "completeness_check",
            "purpose": "完整性检查",
            "content": "检查项目需求文档的完整性，包括功能点覆盖、边界条件、异常处理等。输出JSON格式的检查报告。"
        },
        {
            "name": "architecture_init",
            "purpose": "架构初始化",
            "content": "根据项目类型，推荐合适的技术栈和目录结构。输出JSON格式的配置建议。"
        },
    ]
    
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        for tpl in templates:
            # 检查是否已存在
            result = await conn.execute(
                text(f"SELECT id FROM prompt_templates WHERE name = :name"),
                {"name": tpl["name"]}
            )
            if result.fetchone() is None:
                await conn.execute(
                    text("""
                        INSERT INTO prompt_templates (name, purpose, content, enabled)
                        VALUES (:name, :purpose, :content, true)
                    """),
                    tpl
                )
