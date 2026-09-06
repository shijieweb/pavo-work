"""AI服务。"""

import json
import logging
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.prompt import PromptTemplate

logger = logging.getLogger(__name__)


class AIService:
    """AI服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def optimize_project_description(self, project_id: int) -> dict:
        """优化项目描述。

        Args:
            project_id: 项目ID

        Returns:
            优化结果
        """
        project = await self._get_project(project_id)
        if project is None:
            return {"success": False, "message": "项目不存在"}

        prompt_template = await self._get_prompt_template("project_description_optimize")
        if prompt_template is None:
            return {"success": False, "message": "提示词模板不存在"}

        prompt = self._format_prompt(prompt_template.content, {
            "project_name": project.name,
            "current_description": project.description or "",
        })

        result = await self._call_ai_api(prompt)

        if result.get("success"):
            await self._save_optimized_data(project_id, result.get("optimized_data", {}))
            return result
        return result

    async def generate_project_description(self, project_name: str, user_input: str) -> dict:
        """根据项目名称生成项目简介。

        Args:
            project_name: 项目名称
            user_input: 用户输入的简要描述

        Returns:
            生成结果
        """
        prompt_template = await self._get_prompt_template("project_generate_description")
        if prompt_template is None:
            return {"success": False, "message": "提示词模板不存在"}

        prompt = self._format_prompt(prompt_template.content, {
            "project_name": project_name,
            "user_input": user_input,
        })

        result = await self._call_ai_api(prompt)

        if result.get("success"):
            return {
                "success": True,
                "message": "生成成功",
                "generated_description": result.get("optimized_data", {}).get("description", ""),
                "suggestion": result.get("optimized_data", {}).get("suggestion", ""),
            }
        return result

    async def _get_project(self, project_id: int) -> Optional[Project]:
        """获取项目。"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_prompt_template(self, name: str) -> Optional[PromptTemplate]:
        """获取提示词模板。"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.enabled == True,
            )
        )
        return result.scalar_one_or_none()

    def _format_prompt(self, template: str, variables: dict) -> str:
        """格式化提示词。"""
        prompt = template
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value or ""))
        return prompt

    async def _call_ai_api(self, prompt: str) -> dict:
        """调用AI API。"""
        from app.services.setting_service import SettingService
        from app.core.security import decrypt_api_key

        setting_service = SettingService(self.db)
        setting = await setting_service.get_setting()

        if setting is None or not setting.ai_api_url or not setting.ai_api_key:
            return {"success": False, "message": "未配置AI API"}

        # 解密API Key
        api_key = decrypt_api_key(setting.ai_api_key.encode())
        model = setting.ai_model_name or "gpt-4o-mini"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{setting.ai_api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                optimized_data = json.loads(content)
                return {
                    "success": True,
                    "message": "生成成功",
                    "optimized_data": optimized_data,
                }
        except Exception as e:
            logger.error(f"AI API调用失败: {e}")
            return {"success": False, "message": f"AI API调用失败: {str(e)}"}

    async def _save_optimized_data(self, project_id: int, data: dict) -> None:
        """保存优化数据到项目。"""
        project = await self._get_project(project_id)
        if project is None:
            return

        if "description" in data:
            project.description = data["description"]
        if "target_users" in data:
            project.set_target_users(data["target_users"])
        if "core_functions" in data:
            project.set_core_functions(data["core_functions"])
        if "key_scenarios" in data:
            project.set_key_scenarios(data["key_scenarios"])

        await self.db.commit()

    async def _get_project(self, project_id: int) -> Optional[Project]:
        """获取项目。"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_prompt_template(self, name: str) -> Optional[PromptTemplate]:
        """获取提示词模板。"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.enabled == True,
            )
        )
        return result.scalar_one_or_none()

    def _format_prompt(self, template: str, variables: dict) -> str:
        """格式化提示词。"""
        prompt = template
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value or ""))
        return prompt

    async def _call_ai_api(self, prompt: str) -> dict:
        """调用AI API。"""
        from app.services.setting_service import SettingService
        from app.core.security import decrypt_api_key

        setting_service = SettingService(self.db)
        setting = await setting_service.get_setting()

        if setting is None or not setting.ai_api_url or not setting.ai_api_key:
            return {"success": False, "message": "未配置AI API"}

        # 解密API Key
        api_key = decrypt_api_key(setting.ai_api_key.encode())
        model = setting.ai_model_name or "gpt-4o-mini"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{setting.ai_api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                optimized_data = json.loads(content)
                return {
                    "success": True,
                    "message": "优化成功",
                    "optimized_data": optimized_data,
                }
        except Exception as e:
            logger.error(f"AI API调用失败: {e}")
            return {"success": False, "message": f"AI API调用失败: {str(e)}"}

    async def _save_optimized_data(self, project_id: int, data: dict) -> None:
        """保存优化数据到项目。"""
        project = await self._get_project(project_id)
        if project is None:
            return

        if "description" in data:
            project.description = data["description"]
        if "target_users" in data:
            project.set_target_users(data["target_users"])
        if "core_functions" in data:
            project.set_core_functions(data["core_functions"])
        if "key_scenarios" in data:
            project.set_key_scenarios(data["key_scenarios"])

        await self.db.commit()
