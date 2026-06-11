# Codex / OpenCode 工具集成配置

## Claude Code

项目根目录的 `.mcp.json` 已配置好，Claude Code 启动时自动发现工具。

也可以在 `~/.claude/settings.json` 中全局配置：

```json
{
  "mcpServers": {
    "agentflow-tools": {
      "command": "python",
      "args": ["-m", "agentflow.cli", "mcp-server"],
      "cwd": "/path/to/agentflow"
    }
  }
}
```

验证：在 Claude Code 中输入 `/mcp` 应该能看到 `agentflow-tools`。

## Codex (OpenAI)

Codex 通过 HTTP 调用工具。先启动 API 服务：

```bash
agentflow serve --port 8000
```

然后在 Codex 配置中指定工具 endpoint：

```bash
# codex.json 或环境变量
export OPENAI_TOOLS_URL=http://localhost:8000/api/v1/tools
export OPENAI_TOOL_CALL_URL=http://localhost:8000/api/v1/tools
```

工具调用流程：
1. `GET /api/v1/tools` → 获取 OpenAI function-calling 格式的工具列表
2. `POST /api/v1/tools/{tool_name}/call` → 直接调用工具

## OpenCode (Cursor / 其他 MCP 工具)

OpenCode 原生支持 MCP 协议。在项目根目录创建 `.opencode.yaml`：

```yaml
mcp:
  servers:
    agentflow-tools:
      command: python
      args: ["-m", "agentflow.cli", "mcp-server"]
      description: AgentFlow 工具集
```

## 启动方式

| 工具 | 传输 | 启动命令 |
|------|------|----------|
| Claude Code | MCP stdio | `agentflow mcp-server` |
| Codex | HTTP/REST | `agentflow serve` |
| OpenCode | MCP stdio | `agentflow mcp-server` |
| 远程工具 | MCP SSE | `agentflow mcp-server --http --port 8766` |
