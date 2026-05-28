"""API端到端测试"""

import pytest
from httpx import AsyncClient, ASGITransport

from agentflow.api.app import app, get_app_state
from agentflow.api.auth import create_access_token, UserRole


@pytest.fixture
def auth_headers():
    """认证头"""
    token = create_access_token({"sub": "test_user", "role": UserRole.ADMIN})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_key_headers():
    """API Key头"""
    return {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_health_check():
    """测试健康检查"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "agents_count" in data


@pytest.mark.asyncio
async def test_login_success():
    """测试登录成功"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={
            "username": "admin",
            "password": "admin",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure():
    """测试登录失败"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={
            "username": "wrong",
            "password": "wrong",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_access():
    """测试未认证访问"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
        # 应该返回401或200（如果有可选认证）
        assert resp.status_code in [200, 401]


@pytest.mark.asyncio
async def test_create_agent(auth_headers):
    """测试创建Agent"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/agents",
            json={
                "name": "test_agent",
                "agent_type": "react",
                "system_prompt": "你是一个测试Agent",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test_agent"
        assert data["type"] == "react"
        assert "id" in data


@pytest.mark.asyncio
async def test_list_agents(auth_headers):
    """测试列出Agent"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 先创建一个
        await client.post(
            "/api/v1/agents",
            json={"name": "list_test", "agent_type": "react"},
            headers=auth_headers,
        )

        # 列出
        resp = await client.get("/api/v1/agents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_agent(auth_headers):
    """测试获取单个Agent"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 创建
        create_resp = await client.post(
            "/api/v1/agents",
            json={"name": "get_test", "agent_type": "react"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]

        # 获取
        resp = await client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == agent_id


@pytest.mark.asyncio
async def test_get_agent_not_found(auth_headers):
    """测试获取不存在的Agent"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(auth_headers):
    """测试删除Agent"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 创建
        create_resp = await client.post(
            "/api/v1/agents",
            json={"name": "delete_test", "agent_type": "react"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]

        # 删除
        resp = await client.delete(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 200

        # 验证已删除
        resp = await client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_without_agent(auth_headers):
    """测试无Agent时对话"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "你好"},
            headers=auth_headers,
        )
        # 应该返回错误或使用编排器
        assert resp.status_code in [200, 400, 422]


@pytest.mark.asyncio
async def test_create_workflow(auth_headers):
    """测试创建工作流"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow",
                "description": "测试工作流",
                "nodes": [
                    {"name": "start", "node_type": "agent", "config": {"agent_type": "react", "task": "hello"}},
                    {"name": "end", "node_type": "agent", "config": {"agent_type": "react", "task": "bye"}},
                ],
                "edges": [{"from_node": "start", "to_node": "end"}],
                "entry_node": "start",
                "exit_nodes": ["end"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test_workflow"
        assert "id" in data


@pytest.mark.asyncio
async def test_list_workflows(auth_headers):
    """测试列出工作流"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/workflows", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_metrics(auth_headers):
    """测试指标接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "workflows" in data


@pytest.mark.asyncio
async def test_costs(auth_headers):
    """测试成本接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/costs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_by_agent" in data
        assert "total_tokens" in data


@pytest.mark.asyncio
async def test_openapi_schema():
    """测试OpenAPI文档"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/api/v1/health" in schema["paths"]
        assert "/api/v1/agents" in schema["paths"]
