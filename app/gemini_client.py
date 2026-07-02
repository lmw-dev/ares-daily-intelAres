import os
from google import genai
from app.config import settings

def get_gemini_client() -> genai.Client:
    """
    根据配置初始化并返回 Google GenAI Client。
    - 若 google_genai_use_vertexai 为 True，则以 Vertex AI 模式初始化；
    - 若指定了 gemini_api_key，则以 API Key 模式初始化；
    - 否则，以自适应模式初始化（支持 SDK 自动识别环境变量）。
    """
    if settings.google_genai_use_vertexai:
        # 在 GCP Cloud Run 运行或强制启用 Vertex AI
        project = settings.google_cloud_project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = settings.google_cloud_location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        # 确保在使用 VertexAI 模式时设置了相关 SDK 环境变量
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        if project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ["GOOGLE_CLOUD_LOCATION"] = location
        
        return genai.Client(
            vertexai=True,
            project=project,
            location=location
        )
    elif settings.gemini_api_key:
        # 本地开发 API Key fallback 模式
        return genai.Client(api_key=settings.gemini_api_key)
    else:
        # 兜底自适应发现
        return genai.Client()
