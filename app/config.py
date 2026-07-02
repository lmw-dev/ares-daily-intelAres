import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 支持加载本地 .env 文件
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Google Cloud & Vertex AI 基础配置
    google_genai_use_vertexai: bool = False
    google_cloud_project: Optional[str] = None
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: Optional[str] = None

    # Slack Webhook
    slack_webhook_url: Optional[str] = None

    # Google Cloud Storage 配置
    gcs_bucket: str = "ares-daily-intel-reports"

    # 运行与成本预算控制
    dry_run: bool = True
    max_matches: int = 1
    max_grounded_prompts_per_run: int = 20

# 实例化全局配置对象
settings = Settings()
