FROM python:3.10-slim

WORKDIR /app

# 复制依赖文件
COPY pyproject.toml .
COPY src/ src/

# 安装依赖
RUN pip install --no-cache-dir -e .

# 下载spaCy英文模型
RUN python -m spacy download en_core_web_sm

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app
USER app

# 设置工作目录
WORKDIR /home/app

# 默认命令
CMD ["python", "-m", "notion_vocabulary"]