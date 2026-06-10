# v0.3.0 - 重大质量升级

## 核心修复（13个critical bug）

- **配置模型**：所有Settings模型添加extra=ignore，.env中未知变量不再导致启动崩溃
- **Agent循环**：从3-4次LLM调用/步重写为单次原生工具调用循环
- **工作流引擎**：实现真实DAG调度器，支持fan-out/fan-in、条件跳过传播、可恢复的resume()
- **Supervisor模式**：向LLM展示agent名称+能力描述，不再暴露UUID
- **LLM配置传播**：agent现在从.env继承provider/key/base_url
- **沙箱安全**：AST静态分析替代字符串黑名单，阻断getattr/dunder逃逸
- **RAG向量检索**：实现真实向量嵌入（OpenAI/sentence-transformers），保留TF-IDF兜底
- **长期记忆**：延迟初始化的长期召回替代注入式短期重复
- **LLM缓存**：默认关闭（之前在agent循环中导致静默错误）
- **.env.example**：修正变量前缀以匹配config模型
- **auth.py**：datetime.utcnow()替换为timezone-aware的datetime.now(UTC)
- **清理emoji**：全项目移除emoji字符，修复UI页面缩进错误
- **eval_page**：修复with块过度缩进的IndentationError

## 新增功能

- 8个LLM Provider（OpenAI/Anthropic/Gemini/DeepSeek/Qwen/Zhipu/MiMo/Local）
- UI重构（app.py 1062行减至570行，拆分为chat_page/workflow_page/monitor_page三个独立模块）
- 4个examples的README文档（code_review/customer_service/data_analysis/index）
- 18个新LLM单元测试（覆盖Provider枚举、Factory路由、MockClient、缓存淘汰等）

## 测试状态

- 143 passed, 0 failed, 1 skipped（anthropic未安装）
- 从 102 passed / 12 failed 升级到 143 passed / 0 failed

## 真实LLM端到端验证

使用 MiMo v2.5 Pro 验证：

- 简单对话：`"2+3?"` -> `"5"` （9.2s，2432 tokens）
- 工具调用：`"sqrt(144)+10"` -> 计算器工具 -> `"22"`
- 多Agent编排：Planner -> Coder 实现斐波那契，输出已验证
- 工作流DAG：Agent审查代码 -> `"功能正确，建议添加类型提示"`

## 支持的LLM Provider

| Provider | 协议 |
|----------|------|
| OpenAI | 原生SDK |
| Anthropic | 原生SDK |
| Gemini | google-generativeai |
| DeepSeek | OpenAI兼容 |
| Qwen | OpenAI兼容 |
| Zhipu | OpenAI兼容 |
| MiMo | OpenAI兼容 |
| Local/Ollama | OpenAI兼容 |

## 文档更新

- docs/architecture.md：更新代码示例以反映原生工具调用循环和AST沙箱
- docs/quickstart.md：新增快速入门指南（CLI/API/Streamlit UI/多Agent/工作流）
