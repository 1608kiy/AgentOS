# Changelog

## [0.2.0] - 2026-06-09

### Added
- 流式输出（单Agent + 多Agent编排）
- 对话持久化（JSON文件）
- 对话管理（新建/切换/删除/重命名/搜索/置顶/标签）
- Agent管理（创建/删除/6种类型/预设模板）
- 工具调用可视化
- 对话导出Markdown
- 向量RAG（TF-IDF + 余弦相似度）
- 文档知识库上传
- MiMo 推理模型兼容
- 监控仪表盘（Token/成本/自动刷新）
- 工作流设计器 + 模板
- API设置页
- 新手引导
- 错误重试按钮
- Agent上下文隔离
- 日志文件输出
- API文档（Swagger/ReDoc）
- GitHub Actions CI

### Fixed
- Windows GBK编码崩溃
- tool_call_id缺失导致400错误
- stream_chat不保存assistant消息
- _should_answer降级误判
- 对话切换不重置Agent上下文
- 错误路径不保存对话
- .env路径解析错误

## [0.1.0] - 2026-01-01

### Added
- 初始版本
- ReAct Agent系统
- 多Agent编排（串行/并行/辩论/主管）
- DAG工作流引擎
- FastAPI REST API
- Streamlit UI
- JWT + API Key认证
- 工具系统（计算器/文件读写/代码执行/API调用）
- 评估框架
- 插件系统
