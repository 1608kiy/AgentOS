"""Streamlit UI - AgentFlow 多Agent协作平台（企业级增强版）"""

from __future__ import annotations

import asyncio
from datetime import datetime

import streamlit as st

from agentflow.agents.base import (
    AgentConfig,
    CoderAgent,
    ContentFilterMiddleware,
    CostTrackerMiddleware,
    PlannerAgent,
    ReActAgent,
    ResearcherAgent,
    ReviewerAgent,
    SummarizerAgent,
)
from agentflow.memory.manager import MemoryManager
from agentflow.tools.base import create_default_registry
from agentflow.workflow.engine import DefaultNodeExecutor, WorkflowEngine
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy

# ============ 页面配置 ============
st.set_page_config(
    page_title="AgentFlow",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============ 全局CSS ============
DARK_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; background: #0f172a; color: #e2e8f0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

    .top-nav {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%);
        padding: 12px 30px; border-radius: 0 0 16px 16px; margin: -1rem -1rem 1.5rem -1rem;
        display: flex; align-items: center; justify-content: space-between;
    }
    .top-nav h1 { color: white; font-size: 1.4rem; font-weight: 700; margin: 0; }
    .top-nav .badge { background: rgba(255,255,255,0.15); color: #a78bfa; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; }

    .metric-card {
        background: linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%); color: white;
        border-radius: 16px; padding: 24px; text-align: center;
        box-shadow: 0 8px 32px rgba(76, 29, 149, 0.4); transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-4px); }
    .metric-card .value { font-size: 2.5rem; font-weight: 700; margin: 8px 0; }
    .metric-card .label { font-size: 0.85rem; opacity: 0.9; }
    .metric-card.green { background: linear-gradient(135deg, #064e3b 0%, #059669 100%); }
    .metric-card.orange { background: linear-gradient(135deg, #7c2d12 0%, #ea580c 100%); }
    .metric-card.blue { background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); }

    .agent-card {
        background: #1e293b; border: 1px solid #334155; border-radius: 12px;
        padding: 16px; margin: 8px 0; transition: all 0.2s;
    }
    .agent-card:hover { border-color: #818cf8; box-shadow: 0 4px 16px rgba(129,140,248,0.2); }
    .agent-card .agent-name { font-weight: 600; color: #e2e8f0; }
    .agent-card .agent-type { color: #94a3b8; font-size: 0.8rem; }
    .agent-card .agent-status { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; }
    .status-idle { background: #064e3b; color: #6ee7b7; }
    .status-thinking { background: #78350f; color: #fcd34d; }
    .status-acting { background: #1e3a5f; color: #93c5fd; }
    .status-error { background: #7f1d1d; color: #fca5a5; }
    .status-completed { background: #064e3b; color: #6ee7b7; }

    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
</style>
"""

LIGHT_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

    .top-nav {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 12px 30px; border-radius: 0 0 16px 16px; margin: -1rem -1rem 1.5rem -1rem;
        display: flex; align-items: center; justify-content: space-between;
    }
    .top-nav h1 { color: white; font-size: 1.4rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .top-nav .badge { background: rgba(255,255,255,0.15); color: #a78bfa; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; }

    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;
        border-radius: 16px; padding: 24px; text-align: center;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3); transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-4px); }
    .metric-card .value { font-size: 2.5rem; font-weight: 700; margin: 8px 0; }
    .metric-card .label { font-size: 0.85rem; opacity: 0.9; }
    .metric-card.green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .metric-card.orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
    .metric-card.blue { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }

    .agent-card {
        background: white; border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 16px; margin: 8px 0; transition: all 0.2s;
    }
    .agent-card:hover { border-color: #667eea; box-shadow: 0 4px 16px rgba(102,126,234,0.15); }
    .agent-card .agent-name { font-weight: 600; color: #1f2937; }
    .agent-card .agent-type { color: #6b7280; font-size: 0.8rem; }
    .agent-card .agent-status { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; }
    .status-idle { background: #d1fae5; color: #065f46; }
    .status-thinking { background: #fef3c7; color: #92400e; }
    .status-acting { background: #dbeafe; color: #1e40af; }
    .status-error { background: #fee2e2; color: #991b1b; }
    .status-completed { background: #d1fae5; color: #065f46; }

    [data-testid="stSidebar"] { background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%); }
</style>
"""


# ============ 会话状态初始化 ============
def init_session_state():
    if "agents" not in st.session_state:
        st.session_state.agents = {}
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = AgentOrchestrator()
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "current_agent" not in st.session_state:
        st.session_state.current_agent = None
    if "execution_log" not in st.session_state:
        st.session_state.execution_log = []
    if "cost_tracker" not in st.session_state:
        st.session_state.cost_tracker = CostTrackerMiddleware()
    if "workflow_engine" not in st.session_state:
        executor = DefaultNodeExecutor()
        st.session_state.workflow_engine = WorkflowEngine(executor=executor)
    if "workflows" not in st.session_state:
        st.session_state.workflows = {}
    if "total_messages" not in st.session_state:
        st.session_state.total_messages = 0


def create_agent(agent_type: str, name: str, system_prompt: str = ""):
    config = AgentConfig(agent_name=name, system_prompt=system_prompt)
    agent_map = {
        "ReAct Agent": ReActAgent,
        "Planner": PlannerAgent,
        "Researcher": ResearcherAgent,
        "Coder": CoderAgent,
        "Reviewer": ReviewerAgent,
        "Summarizer": SummarizerAgent,
    }
    agent_class = agent_map.get(agent_type, ReActAgent)
    agent = agent_class(config=config)
    agent.add_middleware(ContentFilterMiddleware())
    agent.add_middleware(st.session_state.cost_tracker)

    st.session_state.agents[agent.id] = agent
    st.session_state.orchestrator.register_agent(agent)

    # 注册到工作流引擎
    st.session_state.workflow_engine.executor.register_agent(name, agent)

    return agent


# ============ 顶部导航 ============
def render_top_nav():
    # 根据主题注入CSS
    if st.session_state.get("dark_mode", False):
        st.markdown(DARK_CSS, unsafe_allow_html=True)
    else:
        st.markdown(LIGHT_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="top-nav">
        <h1>⚡ AgentFlow</h1>
        <span class="badge">v0.2.0 · Enterprise</span>
    </div>
    """, unsafe_allow_html=True)


# ============ 侧边栏 ============
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🎛️ 控制面板")
        st.markdown("---")

        # Agent创建
        st.markdown("#### 创建 Agent")
        agent_type = st.selectbox(
            "类型",
            ["ReAct Agent", "Planner", "Researcher", "Coder", "Reviewer", "Summarizer"],
            label_visibility="collapsed",
        )
        agent_name = st.text_input("名称", f"{agent_type}_{len(st.session_state.agents)+1}", label_visibility="collapsed")
        system_prompt = st.text_area("系统提示", placeholder="定义Agent角色...", height=80, label_visibility="collapsed")

        if st.button("➕ 创建 Agent", use_container_width=True, type="primary"):
            agent = create_agent(agent_type, agent_name, system_prompt)
            st.success(f"✅ {agent.name}")
            st.rerun()

        st.markdown("---")

        # Agent列表
        st.markdown("#### 🤖 Agent 列表")
        if not st.session_state.agents:
            st.caption("暂无Agent，请先创建")
        else:
            for aid, agent in st.session_state.agents.items():
                status_class = f"status-{agent.state.status.value}"
                st.markdown(f"""
                <div class="agent-card">
                    <div class="agent-name">{agent.name}</div>
                    <div class="agent-type">{type(agent).__name__}</div>
                    <span class="agent-status {status_class}">{agent.state.status.value}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # 主题切换
        st.markdown("#### 🎨 主题")
        dark_mode = st.toggle("暗色模式", value=st.session_state.get("dark_mode", False))
        st.session_state.dark_mode = dark_mode

        # 编排策略
        st.markdown("#### 🔄 编排策略")
        strategy = st.selectbox(
            "策略",
            ["sequential", "parallel", "debate", "supervisor"],
            format_func=lambda x: {
                "sequential": "📎 串行执行",
                "parallel": "⚡ 并行执行",
                "debate": "💬 辩论模式",
                "supervisor": "👔 主管模式",
            }.get(x, x),
        )
        st.session_state.strategy = strategy

        strategy_icons = {
            "sequential": "Agent链式执行，前者输出为后者输入",
            "parallel": "所有Agent同时处理同一任务",
            "debate": "多轮讨论，最终得出结论",
            "supervisor": "主管分配任务，Worker执行",
        }
        st.caption(strategy_icons.get(strategy, ""))


# ============ 对话页面 ============
def chat_page():
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 💬 智能对话")

        # 聊天历史
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if "metadata" in msg:
                        with st.expander("📋 执行详情"):
                            st.json(msg["metadata"])

        # 输入
        if prompt := st.chat_input("输入你的任务..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.session_state.total_messages += 1

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            agents = list(st.session_state.agents.values())
            if not agents:
                st.warning("⚠️ 请先在左侧创建至少一个Agent")
                return

            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("🤔 Agent正在思考..."):
                        try:
                            strategy = st.session_state.get("strategy", "sequential")
                            orchestrator = st.session_state.orchestrator
                            orchestrator.strategy = OrchestrationStrategy(strategy)

                            loop = asyncio.new_event_loop()
                            result = loop.run_until_complete(
                                orchestrator.run(prompt, [a.id for a in agents])
                            )

                            st.markdown(result.final_output)

                            metadata = {
                                "strategy": strategy,
                                "duration_ms": round(result.duration_ms, 1),
                                "agents_used": len(agents),
                                "iterations": sum(r.get("iterations", 0) for r in result.results.values() if isinstance(r, dict)),
                            }
                            with st.expander("📋 执行详情"):
                                st.json(result.to_dict())

                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": result.final_output,
                                "metadata": metadata,
                            })
                            st.session_state.total_messages += 1

                            # 记录执行日志
                            st.session_state.execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "task": prompt[:100],
                                "strategy": strategy,
                                "duration_ms": round(result.duration_ms, 1),
                                "status": "success",
                            })

                        except Exception as e:
                            st.error(f"❌ 执行错误: {e}")
                            st.session_state.execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "task": prompt[:100],
                                "strategy": strategy,
                                "status": "error",
                                "error": str(e),
                            })

    with col2:
        st.markdown("### 📊 实时状态")

        # 实时指标
        agents = list(st.session_state.agents.values())
        active = sum(1 for a in agents if a.state.status.value != "idle")
        total_tokens = st.session_state.cost_tracker.get_usage()

        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Agent数量</div>
            <div class="value">{len(agents)}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card green">
            <div class="label">对话轮数</div>
            <div class="value">{st.session_state.total_messages}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card orange">
            <div class="label">Token用量</div>
            <div class="value">{sum(total_tokens.values()):,}</div>
        </div>
        """, unsafe_allow_html=True)

        # 最近执行日志
        st.markdown("#### 📝 最近执行")
        if st.session_state.execution_log:
            for log in st.session_state.execution_log[-5:][::-1]:
                icon = "✅" if log["status"] == "success" else "❌"
                st.caption(f"{icon} {log['task']} ({log['duration_ms']}ms)")
        else:
            st.caption("暂无执行记录")


# ============ 工作流设计器页面 ============
def workflow_page():
    st.markdown("### 🔧 工作流设计器")

    tab1, tab2, tab3 = st.tabs(["🎨 可视化设计", "🧩 模板库", "📝 JSON定义"])

    with tab1:
        from agentflow.ui.components.workflow_designer import render_workflow_designer
        st.caption("双击节点编辑 | Shift+拖拽连线 | 拖拽移动节点")
        render_workflow_designer(height=500)

    with tab2:
        st.markdown("#### 🧩 工作流模板")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""<div class="agent-card"><div class="agent-name">🎯 智能客服</div><div class="agent-type">意图识别 → 路由 → 处理 → 总结</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_cs"):
                _create_customer_service_workflow()
        with col2:
            st.markdown("""<div class="agent-card"><div class="agent-name">🔍 代码审查</div><div class="agent-type">安全 → 质量 → 性能 → 评审</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_cr"):
                _create_code_review_workflow()
        with col3:
            st.markdown("""<div class="agent-card"><div class="agent-name">📊 数据分析</div><div class="agent-type">规划 → 分析 → 报告</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_da"):
                _create_data_analysis_workflow()

        st.markdown("---")
        st.markdown("#### 已创建工作流")
        if st.session_state.workflows:
            for wf_id, wf in st.session_state.workflows.items():
                with st.expander(f"📋 {wf.name}"):
                    st.json(wf.to_dict())
        else:
            st.info("暂无工作流，请使用上方模板创建")

    with tab3:
        st.markdown("#### JSON方式创建工作流")
        wf_json = st.text_area(
            "工作流定义",
            height=300,
            placeholder='{\n  "name": "my_workflow",\n  "nodes": [...],\n  "edges": [...]\n}',
        )
        if st.button("解析并创建"):
            try:
                import json
                data = json.loads(wf_json)
                st.success("✅ 解析成功")
            except Exception as e:
                st.error(f"❌ JSON解析错误: {e}")


def _create_customer_service_workflow():
    from agentflow.workflow.engine import WorkflowBuilder, NodeType
    builder = WorkflowBuilder("智能客服", "用户咨询 → 意图识别 → 专业处理 → 总结")
    builder.add_agent_node("意图识别", "Planner", "分析用户意图")
    builder.add_agent_node("订单处理", "ReAct Agent", "处理订单问题")
    builder.add_agent_node("技术支持", "Coder", "处理技术问题")
    builder.add_agent_node("销售咨询", "Researcher", "处理销售问题")
    builder.add_agent_node("总结回复", "Summarizer", "整合回复")
    builder.connect("意图识别", "订单处理")
    builder.connect("意图识别", "技术支持")
    builder.connect("意图识别", "销售咨询")
    builder.connect("订单处理", "总结回复")
    builder.connect("技术支持", "总结回复")
    builder.connect("销售咨询", "总结回复")
    builder.set_entry("意图识别")
    builder.set_exit("总结回复")
    wf = builder.build()
    st.session_state.workflows[wf.id] = wf
    st.rerun()


def _create_code_review_workflow():
    from agentflow.workflow.engine import WorkflowBuilder, NodeType
    builder = WorkflowBuilder("代码审查", "提交代码 → 多维度审查 → 综合报告")
    builder.add_agent_node("安全扫描", "Reviewer", "检查安全漏洞")
    builder.add_agent_node("质量检查", "Reviewer", "检查代码质量")
    builder.add_agent_node("性能分析", "Reviewer", "分析性能问题")
    builder.add_agent_node("综合评审", "Summarizer", "整合审查结果")
    builder.connect("安全扫描", "综合评审")
    builder.connect("质量检查", "综合评审")
    builder.connect("性能分析", "综合评审")
    builder.set_entry("安全扫描")
    builder.set_exit("综合评审")
    wf = builder.build()
    st.session_state.workflows[wf.id] = wf
    st.rerun()


def _create_data_analysis_workflow():
    from agentflow.workflow.engine import WorkflowBuilder, NodeType
    builder = WorkflowBuilder("数据分析", "需求 → 规划 → 分析 → 报告")
    builder.add_agent_node("分析规划", "Planner", "制定分析计划")
    builder.add_agent_node("数据分析", "Coder", "执行数据分析")
    builder.add_agent_node("报告生成", "Summarizer", "生成分析报告")
    builder.connect("分析规划", "数据分析")
    builder.connect("数据分析", "报告生成")
    builder.set_entry("分析规划")
    builder.set_exit("报告生成")
    wf = builder.build()
    st.session_state.workflows[wf.id] = wf
    st.rerun()


# ============ 监控面板页面 ============
def monitoring_page():
    st.markdown("### 📊 监控面板")

    # 顶部指标
    col1, col2, col3, col4 = st.columns(4)
    agents = list(st.session_state.agents.values())
    total_tokens = st.session_state.cost_tracker.get_usage()

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Agent总数</div>
            <div class="value">{len(agents)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        active = sum(1 for a in agents if a.state.status.value != "idle")
        st.markdown(f"""
        <div class="metric-card green">
            <div class="label">活跃Agent</div>
            <div class="value">{active}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card orange">
            <div class="label">总Token</div>
            <div class="value">{sum(total_tokens.values()):,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card blue">
            <div class="label">执行次数</div>
            <div class="value">{len(st.session_state.execution_log)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 图表区域
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📈 Agent Token用量")
        if total_tokens:
            try:
                import plotly.express as px
                import pandas as pd
                df = pd.DataFrame([
                    {"Agent": aid[:12], "Tokens": tok}
                    for aid, tok in total_tokens.items()
                ])
                fig = px.bar(df, x="Agent", y="Tokens", color="Tokens",
                           color_continuous_scale="Viridis")
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.bar_chart(total_tokens)
        else:
            st.info("暂无数据")

    with col2:
        st.markdown("#### 📉 执行历史")
        if st.session_state.execution_log:
            try:
                import plotly.express as px
                import pandas as pd
                df = pd.DataFrame(st.session_state.execution_log)
                if "duration_ms" in df.columns:
                    fig = px.line(df, y="duration_ms", title="执行耗时(ms)",
                                markers=True)
                    fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                if "duration_ms" in pd.DataFrame(st.session_state.execution_log).columns:
                    st.line_chart(pd.DataFrame(st.session_state.execution_log)["duration_ms"])
        else:
            st.info("暂无执行记录")

    # 执行状态分布
    if st.session_state.execution_log:
        st.markdown("#### 📊 执行状态分布")
        try:
            import plotly.express as px
            import pandas as pd
            df = pd.DataFrame(st.session_state.execution_log)
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["状态", "数量"]
            fig = px.pie(status_counts, values="数量", names="状态",
                        color_discrete_map={"success": "#10b981", "error": "#ef4444"})
            fig.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass

    # Agent详情
    st.markdown("---")
    st.markdown("#### 🤖 Agent 状态详情")

    if agents:
        for agent in agents:
            with st.expander(f"{agent.name} ({agent.state.status.value})"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("迭代次数", agent.state.iteration)
                with c2:
                    st.metric("消息数", len(agent.conversation))
                with c3:
                    st.metric("Token", agent.get_token_usage())
    else:
        st.info("暂无Agent")


# ============ 主函数 ============
def main():
    init_session_state()
    render_top_nav()
    render_sidebar()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 对话", "🔧 工作流", "📊 监控", "🧪 评估", "🔌 插件"
    ])

    with tab1:
        chat_page()
    with tab2:
        workflow_page()
    with tab3:
        monitoring_page()
    with tab4:
        from agentflow.ui.pages.eval_page import render_eval_page
        render_eval_page()
    with tab5:
        from agentflow.ui.pages.plugin_page import render_plugin_page
        render_plugin_page()


if __name__ == "__main__":
    main()
