# 智能客服系统

基于意图识别的多 Agent 客服系统，自动将用户问题路由到对应的专业 Agent 处理，并由总结 Agent 整合最终回复。

## Agent 与编排策略

- Router (ReActAgent) -- 意图识别与路由（订单/技术/销售）
- OrderService (ReActAgent) -- 订单查询、修改、退款
- TechSupport (ReActAgent) -- 产品使用与故障排除
- Sales (ReActAgent) -- 产品介绍与价格方案
- Summary (ReActAgent) -- 整合回复
- 编排策略: Supervisor（主管模式，由 Router 决定分发到哪个 Agent）

## 运行

```bash
# 前提: 在项目根目录的 .env 中配置 LLM API Key
python examples/customer_service/main.py
```

## 预期输出

依次处理三条测试消息（订单查询、技术问题、销售咨询），每条消息先显示用户输入，再显示客服回复。
