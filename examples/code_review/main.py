"""示例: 代码审查助手 - 多Agent协作"""

from __future__ import annotations

import asyncio
from typing import Any

from agentflow.agents.base import AgentConfig, ReActAgent
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy


class SecurityAgent(ReActAgent):
    """安全扫描Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="SecurityScanner",
            system_prompt="""你是一个安全审查专家。你的职责是：
1. 检查代码中的安全漏洞
2. 识别潜在的注入攻击风险
3. 检查敏感信息泄露
4. 验证输入验证和输出编码

请输出安全审查报告，包括：
- 发现的安全问题
- 风险等级（高/中/低）
- 修复建议""",
        ))
        super().__init__(**kwargs)


class QualityAgent(ReActAgent):
    """质量检查Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="QualityChecker",
            system_prompt="""你是一个代码质量专家。你的职责是：
1. 检查代码风格和规范
2. 评估代码可读性和可维护性
3. 检查命名规范
4. 识别代码异味

请输出质量审查报告，包括：
- 代码风格问题
- 可读性评估
- 改进建议""",
        ))
        super().__init__(**kwargs)


class PerformanceAgent(ReActAgent):
    """性能分析Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="PerformanceAnalyzer",
            system_prompt="""你是一个性能优化专家。你的职责是：
1. 识别性能瓶颈
2. 检查算法复杂度
3. 评估资源使用
4. 提供优化建议

请输出性能分析报告，包括：
- 性能问题
- 优化建议
- 预期收益""",
        ))
        super().__init__(**kwargs)


class ReviewerAgent(ReActAgent):
    """综合评审Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig.from_env(
            agent_name="CodeReviewer",
            system_prompt="""你是一个代码审查负责人。你的职责是：
1. 整合各个专家的意见
2. 生成综合审查报告
3. 给出最终评审结论
4. 提供优先级建议

请输出综合审查报告。""",
        ))
        super().__init__(**kwargs)


class CodeReviewSystem:
    """代码审查系统"""

    def __init__(self):
        # 创建Agent
        self.security = SecurityAgent()
        self.quality = QualityAgent()
        self.performance = PerformanceAgent()
        self.reviewer = ReviewerAgent()

        # 创建编排器 - 先并行审查，再综合评审
        self.orchestrator = AgentOrchestrator(
            strategy=OrchestrationStrategy.PARALLEL
        )
        self.orchestrator.register_agents([
            self.security,
            self.quality,
            self.performance,
            self.reviewer,
        ])

    async def review(self, code: str) -> str:
        """审查代码"""
        # 第一阶段：并行审查
        parallel_result = await self.orchestrator.run(
            f"请审查以下代码:\n\n```python\n{code}\n```",
            agent_ids=[
                self.security.id,
                self.quality.id,
                self.performance.id,
            ],
        )

        # 第二阶段：综合评审
        review_result = await self.reviewer.run(
            f"请根据以下审查意见，生成综合审查报告:\n\n{parallel_result.final_output}"
        )

        return review_result.content


async def main():
    """主函数"""
    # 示例代码
    sample_code = '''
def process_user_input(user_input):
    # 直接执行用户输入
    result = eval(user_input)
    return result

def get_user_data(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def calculate_fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib
'''

    print("=" * 60)
    print("代码审查系统")
    print("=" * 60)
    print(f"\n待审查代码:\n{sample_code}")
    print("-" * 60)

    system = CodeReviewSystem()
    report = await system.review(sample_code)

    print(f"\n审查报告:\n{report}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
