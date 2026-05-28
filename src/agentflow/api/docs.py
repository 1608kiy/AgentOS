"""API文档增强"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


API_DESCRIPTION = """
# AgentFlow API

企业级多Agent协作平台API

## 功能特性

- **Agent管理**: 创建、查询、删除Agent
- **对话接口**: 支持单Agent和多Agent编排对话
- **工作流引擎**: 创建和执行DAG工作流
- **实时通信**: WebSocket流式输出
- **认证鉴权**: JWT + API Key双模式认证

## 快速开始

### 1. 获取Token

```bash
curl -X POST /api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### 2. 创建Agent

```bash
curl -X POST /api/v1/agents \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my_agent", "agent_type": "react"}'
```

### 3. 对话

```bash
curl -X POST /api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "agent_id": "<agent_id>"}'
```

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 请求参数错误 |
| 500 | 服务器内部错误 |
"""


def enhance_api_docs(app: FastAPI) -> None:
    """增强API文档"""
    app.description = API_DESCRIPTION

    app.openapi_tags = [
        {
            "name": "认证",
            "description": "用户认证和Token管理",
        },
        {
            "name": "Agent",
            "description": "Agent的创建、查询、删除和执行",
        },
        {
            "name": "对话",
            "description": "与Agent进行对话",
        },
        {
            "name": "工作流",
            "description": "工作流的创建和执行",
        },
        {
            "name": "编排",
            "description": "多Agent编排执行",
        },
        {
            "name": "系统",
            "description": "健康检查和监控指标",
        },
    ]

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - API文档",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )
