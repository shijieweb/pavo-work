"""添加prompt_templates表。

Revision ID: 001_initial
Revises:
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库结构。"""
    # 创建global_settings表
    op.create_table(
        "global_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ai_api_url", sa.String(500), nullable=True),
        sa.Column("ai_api_key", sa.Text(), nullable=True),
        sa.Column("ai_model_name", sa.String(100), nullable=True),
        sa.Column("token", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 创建projects表
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_users", sa.Text(), nullable=True),
        sa.Column("core_functions", sa.Text(), nullable=True),
        sa.Column("key_scenarios", sa.Text(), nullable=True),
        sa.Column("architecture_snapshot", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 创建prompt_templates表
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 创建project_initialization表
    op.create_table(
        "project_initialization",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_tree", sa.JSON(), nullable=True),
        sa.Column("readme_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 插入默认提示词模板
    default_templates = [
        (
            "project_description_optimize",
            "项目描述优化",
            """你是一位资深产品经理。请帮助用户优化项目描述，使其更专业、结构化。

【项目基本信息】
名称：{project_name}
当前描述：{current_description}

【优化要求】
1. 保持原意，提升表达清晰度
2. 使用结构化格式（目标用户、核心功能、关键场景）
3. 语言简洁专业，避免空泛描述
4. 输出JSON格式：{"description": "...", "target_users": [...], "core_functions": [...], "key_scenarios": [...]}""",
        ),
        (
            "story_expansion",
            "故事扩展",
            """你是一位产品分析师。请基于以下项目信息，扩展用户故事。

【项目信息】
名称：{project_name}
描述：{project_description}
目标用户：{target_users}

【输出要求】
输出JSON格式，包含多个用户故事：
{{
  "stories": [
    {{
      "title": "故事标题",
      "description": "作为[角色]，我希望[行为]，以便[价值]",
      "acceptance_criteria": ["标准1", "标准2"]
    }}
  ]
}}""",
        ),
        (
            "dev_doc_generation",
            "开发文档生成",
            """你是一位技术架构师。请为以下项目生成开发文档。

【项目信息】
名称：{project_name}
核心功能：{core_functions}

【输出要求】
包含：
1. 技术选型建议
2. 目录结构规划
3. 核心模块设计
4. API接口设计概要""",
        ),
        (
            "test_doc_generation",
            "测试文档生成",
            """你是一位测试工程师。请为以下功能生成测试文档。

【功能描述】
{feature_description}

【输出要求】
包含：
1. 测试场景清单
2. 测试用例设计
3. 边界条件测试
4. 异常流程测试""",
        ),
        (
            "acceptance_doc_generation",
            "验收文档生成",
            """你是一位产品经理。请生成项目验收文档。

【项目信息】
名称：{project_name}
核心功能：{core_functions}
关键场景：{key_scenarios}

【输出要求】
1. 验收标准
2. 功能测试清单
3. 性能测试要求
4. 兼容性测试范围""",
        ),
        (
            "integrity_check",
            "完整性检查",
            """你是一位质量保障专家。请检查项目需求的完整性。

【项目信息】
名称：{project_name}
描述：{project_description}

【检查维度】
1. 需求是否清晰无歧义
2. 功能是否完整无遗漏
3. 边界条件是否覆盖
4. 异常情况是否考虑
5. 非功能需求是否明确""",
        ),
        (
            "arch_init",
            "架构初始化",
            """你是一位系统架构师。请为以下项目设计初始架构。

【项目信息】
名称：{project_name}
核心功能：{core_functions}
技术约束：{tech_constraints}

【输出要求】
1. 架构图说明
2. 模块划分
3. 数据模型设计
4. 接口规范
5. 部署方案概要""",
        ),
    ]

    for name, purpose, content in default_templates:
        op.insert("prompt_templates").values(
            name=name,
            purpose=purpose,
            content=content,
            enabled=True,
        )


def downgrade() -> None:
    """降级数据库结构。"""
    op.drop_table("project_initialization")
    op.drop_table("prompt_templates")
    op.drop_table("projects")
    op.drop_table("global_settings")
