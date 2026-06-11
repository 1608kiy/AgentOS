"""示例: 数据分析流水线 - 多Agent协作"""

from __future__ import annotations

import asyncio
from typing import Any

from agentflow.agents.base import AgentConfig, ReActAgent
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy


class PlannerAgent(ReActAgent):
    """分析规划Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="AnalysisPlanner",
            system_prompt="""你是一个数据分析规划专家。你的职责是：
1. 理解分析需求
2. 制定分析计划
3. 确定需要的指标和维度
4. 规划分析步骤

请输出结构化的分析计划。""",
        ))
        super().__init__(**kwargs)


class DataAgent(ReActAgent):
    """数据提取Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="DataExtractor",
            system_prompt="""你是一个数据提取专家。你的职责是：
1. 根据分析需求提取数据
2. 清洗和预处理数据
3. 验证数据质量
4. 输出可用的数据集

请输出数据提取结果。""",
        ))
        super().__init__(**kwargs)


class AnalystAgent(ReActAgent):
    """数据分析Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="DataAnalyst",
            system_prompt="""你是一个数据分析师。你的职责是：
1. 执行统计分析
2. 识别数据模式和趋势
3. 发现异常和洞察
4. 验证假设

请输出分析结果。""",
        ))
        super().__init__(**kwargs)


class VisualizerAgent(ReActAgent):
    """可视化Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="Visualizer",
            system_prompt="""你是一个数据可视化专家。你的职责是：
1. 选择合适的图表类型
2. 设计可视化方案
3. 生成图表代码
4. 优化展示效果

请输出可视化方案和代码。""",
        ))
        super().__init__(**kwargs)


class ReporterAgent(ReActAgent):
    """报告生成Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="ReportGenerator",
            system_prompt="""你是一个报告撰写专家。你的职责是：
1. 整合分析结果
2. 生成清晰的报告
3. 提供建议和结论
4. 确保报告专业易懂

请输出最终分析报告。""",
        ))
        super().__init__(**kwargs)


class DataAnalysisSystem:
    """数据分析系统"""

    def __init__(self):
        # 创建Agent
        self.planner = PlannerAgent()
        self.data = DataAgent()
        self.analyst = AnalystAgent()
        self.visualizer = VisualizerAgent()
        self.reporter = ReporterAgent()

        # 创建编排器
        self.orchestrator = AgentOrchestrator(
            strategy=OrchestrationStrategy.SEQUENTIAL
        )
        self.orchestrator.register_agents([
            self.planner,
            self.data,
            self.analyst,
            self.visualizer,
            self.reporter,
        ])

    async def analyze(self, requirement: str) -> str:
        """执行数据分析"""
        result = await self.orchestrator.run(
            requirement,
            agent_ids=[
                self.planner.id,
                self.data.id,
                self.analyst.id,
                self.visualizer.id,
                self.reporter.id,
            ],
        )
        return result.final_output


async def main():
    """主函数"""
    print("=" * 60)
    print("数据分析流水线演示")
    print("=" * 60)

    system = DataAnalysisSystem()

    requirement = """
    分析某电商平台的用户购买行为数据，包括：
    1. 用户购买频次分布
    2. 热门商品类别
    3. 用户留存率
    4. 购买时间分布
    5. 用户价值分层
    """

    print(f"\n分析需求:\n{requirement}")
    print("-" * 60)

    report = await system.analyze(requirement)

    print(f"\n分析报告:\n{report}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
