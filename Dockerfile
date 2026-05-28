# ============ 构建阶段 ============
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用Docker缓存）
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ============ 运行阶段 ============
FROM python:3.12-slim AS runtime

WORKDIR /app

# 创建非root用户
RUN groupadd -r agentflow && useradd -r -g agentflow -d /app -s /sbin/nologin agentflow

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制Python包
COPY --from=builder /install /usr/local

# 复制源代码
COPY src/ src/
COPY examples/ examples/

# 创建数据目录并设置权限
RUN mkdir -p data && chown -R agentflow:agentflow /app

# 切换到非root用户
USER agentflow

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 暴露端口
EXPOSE 8000 8501

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# 默认启动API服务
CMD ["python", "-m", "uvicorn", "agentflow.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
