"""示例: 智能客服系统 - 多Agent协作"""

from __future__ import annotations

import asyncio
from typing import Any

from agentflow.agents.base import AgentConfig, BaseAgent, ReActAgent
from agentflow.workflow.engine import WorkflowBuilder, WorkflowEngine, NodeType
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy


class RouterAgent(ReActAgent):
    """路由Agent - 识别用户意图"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Router",
            system_prompt="""你是一个智能客服路由Agent。你的职责是：
1. 分析用户的问题
2. 识别用户意图
3. 将问题路由到正确的处理Agent

意图类别：
- order: 订单相关（查询、修改、取消订单）
- tech: 技术支持（产品使用、故障排除）
- sales: 销售咨询（产品信息、价格、购买）

请只输出意图类别名称，不要输出其他内容。""",
        ))
        super().__init__(**kwargs)


class OrderAgent(ReActAgent):
    """订单Agent - 处理订单相关问题"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="OrderService",
            system_prompt="""你是一个订单服务Agent。你可以帮助用户：
1. 查询订单状态
2. 修改订单信息
3. 取消订单
4. 处理退款

请根据用户的问题提供详细的帮助。""",
        ))
        super().__init__(**kwargs)


class TechAgent(ReActAgent):
    """技术支持Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="TechSupport",
            system_prompt="""你是一个技术支持Agent。你可以帮助用户：
1. 解答产品使用问题
2. 排除常见故障
3. 提供操作指南
4. 升级到人工支持

请用专业但友好的语气帮助用户。""",
        ))
        super().__init__(**kwargs)


class SalesAgent(ReActAgent):
    """销售Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Sales",
            system_prompt="""你是一个销售Agent。你可以帮助用户：
1. 介绍产品功能
2. 说明价格方案
3. 提供购买建议
4. 处理优惠活动

请用热情专业的态度服务客户。""",
        ))
        super().__init__(**kwargs)


class SummaryAgent(ReActAgent):
    """总结Agent - 整合回复"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Summary",
            system_prompt="""你是一个总结Agent。你的职责是：
1. 整合各个Agent的回复
2. 生成清晰简洁的最终回复
3. 确保回复完整且易于理解

请用友好的语气生成最终回复。""",
        ))
        super().__init__(**kwargs)


class CustomerServiceSystem:
    """智能客服系统"""

    def __init__(self):
        # 创建Agent
        self.router = RouterAgent()
        self.order_agent = OrderAgent()
        self.tech_agent = TechAgent()
        self.sales_agent = SalesAgent()
        self.summary_agent = SummaryAgent()

        # 创建编排器
        self.orchestrator = AgentOrchestrator(
            strategy=OrchestrationStrategy.SUPERVISOR
        )
        self.orchestrator.register_agents([
            self.router,
            self.order_agent,
            self.tech_agent,
            self.sales_agent,
            self.summary_agent,
        ])

    async def handle(self, user_message: str) -> str:
        """处理用户消息"""
        # 使用主管模式
        result = await self.orchestrator.run(
            user_message,
            agent_ids=[
                self.router.id,
                self.order_agent.id,
                self.tech_agent.id,
                self.sales_agent.id,
                self.summary_agent.id,
            ],
        )
        return result.final_output


async def main():
    """主函数"""
    print("=" * 50)
    print("智能客服系统演示")
    print("=" * 50)

    system = CustomerServiceSystem()

    # 测试对话
    test_messages = [
        "我想查询一下我的订单状态，订单号是 ORD-2024-001",
        "这个产品怎么使用？我遇到了一些问题",
        "你们有什么优惠活动吗？",
    ]

    for message in test_messages:
        print(f"\n用户: {message}")
        print("-" * 50)

        response = await system.handle(message)
        print(f"客服: {response}")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
