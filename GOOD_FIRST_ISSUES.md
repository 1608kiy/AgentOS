# Good First Issues - 欢迎贡献

将以下内容复制到 GitHub Issues 中创建。

---

## Issue 1: CI badge 显示在 README

**标题:** feat: add CI status badge to README.md  
**标签:** good first issue, docs  
**描述:**

README.md 顶部的 badges 区域缺少 CI 状态徽章。添加：

```markdown
<img src="https://github.com/1608kiy/AgentOS/actions/workflows/ci.yml/badge.svg" alt="CI">
```

放在 tests badge 旁边即可。

---

## Issue 2: 支持 YAML 格式定义工作流

**标题:** feat: support YAML workflow definition  
**标签:** enhancement, good first issue  
**描述:**

当前工作流只能通过 Python 代码或 JSON 定义。支持 YAML 格式可以让非 Python 用户更方便地配置工作流。

**实现建议:**
- 在 `WorkflowBuilder` 中添加 `from_yaml(path)` 类方法
- 在 UI 的"JSON定义"标签页增加"YAML定义"选项
- 依赖已有的 `pyyaml` 包

---

## Issue 3: 多轮对话记忆持久化

**标题:** feat: persist conversation memory across sessions  
**标签:** enhancement  
**描述:**

当前 Agent 的长期记忆（LongTermMemory）在进程重启后丢失。需要：
- 在 `MemoryManager.initialize()` 中从 SQLite/文件加载已有记忆
- 任务完成后自动持久化到存储
- 已有 `FileSessionStore` 可以参考实现

---

## Issue 4: 添加 Anthropic 集成测试

**标题:** test: add Anthropic integration tests  
**标签:** good first issue, testing  
**描述:**

当前 `tests/unit/test_llm.py` 中 Anthropic 测试因包未安装被 skip。需要：
- 在 `pyproject.toml` 的 `dev` 依赖中添加 `anthropic`
- 确保 CI 中 Anthropic 测试能跑（用 MockLLM 或真正的 API key）
- 至少覆盖：chat、stream、function_call 三条路径

---

## Issue 5: UI 暗色模式支持

**标题:** feat: add dark mode toggle to Streamlit UI  
**标签:** enhancement, good first issue  
**描述:**

`.streamlit/config.toml` 已有暗色主题配置。但用户无法在界面上切换。需要：
- 在侧边栏添加"亮色/暗色"切换按钮
- 切换时修改 `st._config.set_option("theme.base", "dark"/"light")`
- 用 `st.rerun()` 刷新页面

---

## Issue 6: 工作流 JSON 定义真正执行

**标题:** feat: parse and execute workflow from JSON input  
**标签:** enhancement  
**描述:**

UI 的"JSON定义"标签页目前只做 JSON 语法检查，不会真正创建工作流。需要：
- 将 JSON 解析为 `WorkflowDefinition` 对象
- 验证节点类型、边的合法性
- 注册到 `st.session_state.workflows` 以便执行
