# AgentFlow 示例集

本目录包含 AgentFlow 的多 Agent 协作示例，展示不同编排策略的实际应用。

**所有示例均会调用真实 LLM，请先在项目根目录配置 `.env` 文件，填入对应的 API Key。**

## 示例列表

### code_review -- 代码审查助手

多 Agent 并行审查代码的安全性、质量和性能，再由综合评审 Agent 汇总报告。使用 Parallel 编排策略。

```bash
python examples/code_review/main.py
```

### customer_service -- 智能客服系统

基于意图识别的客服路由系统，将订单、技术、销售问题自动分发到专业 Agent 处理。使用 Supervisor 编排策略。

```bash
python examples/customer_service/main.py
```

### data_analysis -- 数据分析流水线

五个 Agent 串行协作，完成从需求理解到报告生成的端到端数据分析。使用 Sequential 编排策略。

```bash
python examples/data_analysis/main.py
```

### demo_code_review.py -- 代码审查演示用例

包含多处安全漏洞（SQL 注入、eval 反序列化、路径穿越、硬编码密钥等）的示例代码，供 code_review 示例审查使用。

### 测试流程.txt

项目测试流程说明文档。
