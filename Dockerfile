FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 写入 .pyc 并启用无缓冲日志输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 复制并安装依赖
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码及数据
COPY app /app/app
COPY data /app/data
COPY prompts /app/prompts

# 默认执行主程序
CMD ["python", "app/main.py"]
