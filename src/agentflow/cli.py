"""CLI入口"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentflow import __version__

app = typer.Typer(
    name="agentflow",
    help="AgentFlow - 企业级多Agent协作平台",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """显示版本信息"""
    console.print(f"[bold blue]AgentFlow[/] v{__version__}")


@app.command()
def run(
    task: str = typer.Argument(..., help="要执行的任务"),
    strategy: str = typer.Option("sequential", help="编排策略: sequential/parallel/debate/supervisor"),
    agents: Optional[str] = typer.Option(None, help="使用的Agent列表，逗号分隔"),
):
    """运行Agent任务"""
    from agentflow.agents.base import ReActAgent, PlannerAgent, ResearcherAgent
    from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy

    console.print(Panel(f"[bold]任务:[/] {task}", title="AgentFlow"))

    # 创建编排器
    strategy_map = {
        "sequential": OrchestrationStrategy.SEQUENTIAL,
        "parallel": OrchestrationStrategy.PARALLEL,
        "debate": OrchestrationStrategy.DEBATE,
        "supervisor": OrchestrationStrategy.SUPERVISOR,
    }
    orchestrator = AgentOrchestrator(strategy=strategy_map.get(strategy, OrchestrationStrategy.SEQUENTIAL))

    # 创建Agent
    planner = PlannerAgent()
    researcher = ResearcherAgent()
    executor = ReActAgent(config=type(planner.config)(agent_name="Executor"))

    orchestrator.register_agents([planner, researcher, executor])

    # 执行
    async def _run():
        result = await orchestrator.run(task)
        return result

    result = asyncio.run(_run())

    # 显示结果
    console.print("\n[bold green]执行结果:[/]")
    console.print(Panel(result.final_output, title="输出"))

    # 显示详细信息
    table = Table(title="Agent执行详情")
    table.add_column("Agent", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("耗时(ms)", justify="right")

    for agent_id, info in result.results.items():
        table.add_row(
            agent_id,
            "完成",
            f"{info.get('duration_ms', 0):.1f}",
        )

    console.print(table)
    console.print(f"\n总耗时: {result.duration_ms:.1f}ms")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="监听地址"),
    port: int = typer.Option(8000, help="监听端口"),
    reload: bool = typer.Option(False, help="自动重载"),
):
    """启动API服务"""
    import uvicorn

    console.print(f"[bold blue]启动API服务[/] http://{host}:{port}")
    uvicorn.run(
        "agentflow.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def ui(
    port: int = typer.Option(8501, help="Streamlit端口"),
):
    """启动Streamlit UI"""
    import subprocess

    console.print(f"[bold blue]启动Streamlit UI[/] http://localhost:{port}")
    subprocess.run([
        "streamlit", "run",
        "src/agentflow/ui/app.py",
        "--server.port", str(port),
    ])


if __name__ == "__main__":
    app()
