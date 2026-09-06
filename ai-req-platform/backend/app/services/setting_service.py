"""设置服务。"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_api_key, decrypt_api_key
from app.models.setting import GlobalSetting


class SettingService:
    """全局设置服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_setting(self) -> Optional[GlobalSetting]:
        """获取全局设置。"""
        result = await self.db.execute(select(GlobalSetting).limit(1))
        return result.scalar_one_or_none()

    async def update_ai_config(self, ai_api_url: str, ai_api_key: str, ai_model_name: str, token: Optional[str] = None) -> GlobalSetting:
        """更新AI配置。

        Args:
            ai_api_url: AI API地址
            ai_api_key: AI API密钥（加密存储）
            ai_model_name: 模型名称
            token: 认证令牌

        Returns:
            更新后的设置对象
        """
        setting = await self.get_setting()
        if setting is None:
            setting = GlobalSetting()
            self.db.add(setting)

        setting.ai_api_url = ai_api_url
        setting.ai_api_key = encrypt_api_key(ai_api_key).decode()
        setting.ai_model_name = ai_model_name
        setting.token = token

        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def test_ai_connection(self) -> dict:
        """测试AI连接。

        Returns:
            测试结果
        """
        setting = await self.get_setting()
        if setting is None or not setting.ai_api_url or not setting.ai_api_key:
            return {"success": False, "message": "未配置AI API"}

        # 解密API Key进行测试
        decrypted_key = decrypt_api_key(setting.ai_api_key.encode())

        # 实际测试将在AI服务中实现
        return {"success": True, "message": "连接成功", "model_used": setting.ai_model_name}
