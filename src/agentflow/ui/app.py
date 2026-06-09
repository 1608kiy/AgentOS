"""Streamlit UI - AgentFlow 多Agent协作平台（企业级增强版）"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

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

# ============ 全局CSS — 简约现代 ============
GLOBAL_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

    /* ===== 基础 ===== */
    .stApp { font-family: 'Inter', sans-serif; background: #fafafa; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

    /* ===== 顶部栏 ===== */
    .top-bar {
        background: white;
        padding: 12px 28px;
        margin: -1rem -1rem 1.2rem -1rem;
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 1px solid #f0f0f0;
    }
    .top-bar h1 {
        font-size: 1.1rem; font-weight: 600; color: #1a1a1a;
        margin: 0; letter-spacing: -0.5px;
    }
    .top-bar .version {
        font-size: 0.7rem; color: #999; font-weight: 400;
        background: #f5f5f5; padding: 3px 10px; border-radius: 10px;
    }

    /* ===== 指标卡片 ===== */
    .metric-card {
        background: white; color: #1a1a1a;
        border: 1px solid #f0f0f0; border-radius: 12px;
        padding: 20px; text-align: center;
    }
    .metric-card .value { font-size: 1.8rem; font-weight: 600; margin: 6px 0; }
    .metric-card .label { font-size: 0.7rem; color: #999; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card.green { border-top: 3px solid #22c55e; }
    .metric-card.orange { border-top: 3px solid #f59e0b; }
    .metric-card.blue { border-top: 3px solid #3b82f6; }

    /* ===== Agent 卡片 ===== */
    .agent-card {
        background: white; border: 1px solid #f0f0f0; border-radius: 10px;
        padding: 12px 14px; margin: 4px 0;
        display: flex; justify-content: space-between; align-items: center;
    }
    .agent-card:hover { border-color: #e0e0e0; }
    .agent-card .agent-name { font-weight: 500; color: #1a1a1a; font-size: 0.85rem; }
    .agent-card .agent-type { color: #aaa; font-size: 0.7rem; }
    .agent-card .agent-status {
        display: inline-block; padding: 2px 8px; border-radius: 6px;
        font-size: 0.65rem; font-weight: 500;
    }
    .status-idle { background: #f0fdf4; color: #16a34a; }
    .status-thinking { background: #fffbeb; color: #d97706; }
    .status-acting { background: #eff6ff; color: #2563eb; }
    .status-error { background: #fef2f2; color: #dc2626; }
    .status-completed { background: #f0fdf4; color: #16a34a; }

    /* ===== 侧边栏 ===== */
    [data-testid="stSidebar"] { background: white; border-right: 1px solid #f0f0f0; }
    [data-testid="stSidebar"] .stMarkdown h4 { font-size: 0.8rem; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-top: 1rem; }

    /* ===== 分割线 ===== */
    hr { border: none; border-top: 1px solid #f0f0f0; margin: 0.8rem 0; }

    /* ===== 按钮 ===== */
    .stButton > button {
        border-radius: 8px; padding: 8px 16px; font-size: 0.82rem;
        font-weight: 500; transition: all 0.15s;
    }
    .stButton > button:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .stButton > button[kind="primary"] { background: #1a1a1a; border-color: #1a1a1a; }
    .stButton > button[kind="secondary"] { background: #f5f5f5; border-color: #e5e5e5; color: #666; }

    /* ===== 输入框 ===== */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea { border-radius: 8px; border-color: #e5e5e5; }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus { border-color: #1a1a1a; box-shadow: 0 0 0 1px #1a1a1a; }

    /* ===== 聊天 ===== */
    [data-testid="stChatMessage"] { border-radius: 12px; }

    /* ===== 选择框 ===== */
    .stSelectbox > div > div { border-radius: 8px; border-color: #e5e5e5; }

    /* ===== Tab ===== */
    .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid #f0f0f0; }
    .stTabs [data-baseweb="tab"] { font-size: 0.85rem; font-weight: 500; color: #999; padding: 12px 24px; }
    .stTabs [aria-selected="true"] { color: #1a1a1a; border-bottom: 2px solid #1a1a1a; }

    /* ===== Expander ===== */
    .streamlit-expanderHeader { font-size: 0.82rem; color: #666; }

    /* ===== 提示 ===== */
    .stSuccess { border-left: 3px solid #22c55e; }
    .stWarning { border-left: 3px solid #f59e0b; }
    .stError { border-left: 3px solid #dc2626; }
    .stInfo { border-left: 3px solid #3b82f6; }

    /* ===== 动画 ===== */
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    .agent-card { animation: fadeIn 0.2s ease; }
</style>
"""


# ============ 数据持久化 ============
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CONV_FILE = DATA_DIR / "conversations.json"


def _save_conversations() -> None:
    """保存对话到文件"""
    DATA_DIR.mkdir(exist_ok=True)
    data = {}
    for cid, conv in st.session_state.conversations.items():
        data[cid] = {
            "name": conv["name"],
            "messages": conv["messages"],
            "created_at": conv["created_at"],
            "pinned": conv.get("pinned", False),
            "tags": conv.get("tags", []),
        }
    CONV_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_conversations() -> dict:
    """从文件加载对话"""
    if CONV_FILE.exists():
        try:
            return json.loads(CONV_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ============ 会话状态初始化 ============
def init_session_state():
    if "agents" not in st.session_state:
        st.session_state.agents = {}
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = AgentOrchestrator()
    if "conversations" not in st.session_state:
        st.session_state.conversations = _load_conversations()
    if "current_conversation_id" not in st.session_state:
        if st.session_state.conversations:
            st.session_state.current_conversation_id = list(st.session_state.conversations.keys())[-1]
        else:
            cid = f"conv_{int(time.time())}"
            st.session_state.current_conversation_id = cid
            st.session_state.conversations[cid] = {
                "name": "新对话",
                "messages": [],
                "created_at": datetime.now().isoformat(),
            }
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
        st.session_state.total_messages = sum(len(c["messages"]) for c in st.session_state.conversations.values())


def get_current_chat() -> dict:
    """获取当前对话"""
    cid = st.session_state.current_conversation_id
    return st.session_state.conversations[cid]


def new_conversation() -> None:
    """新建对话"""
    cid = f"conv_{int(time.time())}"
    st.session_state.conversations[cid] = {
        "name": "新对话",
        "messages": [],
        "created_at": datetime.now().isoformat(),
        "pinned": False,
        "tags": [],
    }
    st.session_state.current_conversation_id = cid
    for agent in st.session_state.agents.values():
        agent.reset()
    _save_conversations()


def create_agent(agent_type: str, name: str, system_prompt: str = ""):
    import os
    from agentflow.core.config import LLMProvider

    provider_name = st.session_state.get("settings_provider", "mimo")
    provider_map = {
        "openai": LLMProvider.OPENAI,
        "anthropic": LLMProvider.ANTHROPIC,
        "local": LLMProvider.LOCAL,
        "mimo": LLMProvider.MIMO,
    }
    provider = provider_map.get(provider_name, LLMProvider.MIMO)

    # 优先从 session_state 读（用户在UI输入的），兜底从 .env 环境变量读
    api_key = st.session_state.get("settings_openai_key", "") or os.environ.get("LLM_API_KEY", "")
    anthropic_key = st.session_state.get("settings_anthropic_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    mimo_key = st.session_state.get("settings_mimo_key", "") or os.environ.get("LLM_API_KEY", "")
    model = st.session_state.get("settings_model") or os.environ.get("LLM_MODEL", "mimo-v2.5-pro")
    temperature = st.session_state.get("settings_temperature", 0.7)
    max_tokens = st.session_state.get("settings_max_tokens", 4096)

    config = AgentConfig(
        agent_name=name,
        system_prompt=system_prompt,
        llm_provider=provider,
        llm_model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if provider_name == "mimo":
        config.llm_api_key = mimo_key
        config.llm_provider = LLMProvider.MIMO
        os.environ["LLM_API_KEY"] = mimo_key
        os.environ["LLM_OPENAI_BASE_URL"] = "https://token-plan-sgp.xiaomimimo.com/v1"
    elif provider_name == "openai":
        config.llm_api_key = api_key
        os.environ["LLM_API_KEY"] = api_key
    elif provider_name == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        config.llm_api_key = anthropic_key

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
    st.session_state.workflow_engine.executor.register_agent(name, agent)

    return agent


# ============ 顶部导航 ============
def render_top_nav():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="top-bar">
        <h1>AgentFlow</h1>
        <span class="version">v0.2</span>
    </div>
    """, unsafe_allow_html=True)


# ============ 侧边栏 ============
def render_sidebar():
    with st.sidebar:
        # ===== 对话管理 =====
        st.markdown("### 对话")
        col_new, col_del = st.columns(2)
        with col_new:
            if st.button("新建", use_container_width=True):
                new_conversation()
                st.rerun()
        with col_del:
            if st.button("清空", use_container_width=True):
                chat = get_current_chat()
                chat["messages"] = []
                for agent in st.session_state.agents.values():
                    agent.reset()
                _save_conversations()
                st.rerun()

        # 搜索框
        search_query = st.text_input("搜索", placeholder="搜索对话...", key="conv_search", label_visibility="collapsed")

        # 对话列表
        convs = st.session_state.conversations
        # 搜索过滤
        search_query = st.session_state.get("conv_search", "")
        display_convs = {}
        for cid, conv in convs.items():
            if not search_query or search_query.lower() in conv["name"].lower():
                display_convs[cid] = conv

        # 置顶优先排序
        sorted_convs = sorted(display_convs.items(), key=lambda x: (not x[1].get("pinned", False), x[1].get("created_at", "")))

        for cid, conv in sorted_convs[-8:][::-1]:
            is_current = cid == st.session_state.current_conversation_id
            msg_count = len(conv["messages"])
            is_pinned = conv.get("pinned", False)

            col_pin, col_name, col_ren, col_del = st.columns([1, 4, 1, 1])
            with col_pin:
                pin_label = "*" if is_pinned else ""
                if st.button(pin_label, key=f"pin_{cid}", help="置顶"):
                    conv["pinned"] = not is_pinned
                    _save_conversations()
                    st.rerun()
            with col_name:
                tags = conv.get("tags", [])
                tag_str = " ".join(tags) if tags else ""
                label = f"{'>' if is_current else ''} {conv['name']} ({msg_count}) {tag_str}"
                if st.button(label, key=f"conv_{cid}", use_container_width=True, type="primary" if is_current else "secondary"):
                    st.session_state.current_conversation_id = cid
                    for agent in st.session_state.agents.values():
                        agent.reset()
                    st.rerun()
            with col_ren:
                if st.button("e", key=f"ren_{cid}", help="重命名"):
                    st.session_state[f"renaming_{cid}"] = True
                    st.rerun()
            with col_del:
                if st.button("x", key=f"del_{cid}", help="删除"):
                    del st.session_state.conversations[cid]
                    if cid == st.session_state.current_conversation_id:
                        if st.session_state.conversations:
                            st.session_state.current_conversation_id = list(st.session_state.conversations.keys())[-1]
                        else:
                            new_conversation()
                    _save_conversations()
                    st.rerun()

            # 重命名输入
            if st.session_state.get(f"renaming_{cid}"):
                new_name = st.text_input("新名称", value=conv["name"], key=f"rn_{cid}")
                # 标签输入
                existing_tags = " ".join(conv.get("tags", []))
                new_tags = st.text_input("标签", value=existing_tags, placeholder="空格分隔", key=f"tags_{cid}")
                c_ok, c_no = st.columns(2)
                with c_ok:
                    if st.button("OK", key=f"rn_ok_{cid}"):
                        conv["name"] = new_name
                        conv["tags"] = new_tags.split() if new_tags.strip() else []
                        st.session_state[f"renaming_{cid}"] = False
                        _save_conversations()
                        st.rerun()
                with c_no:
                    if st.button("取消", key=f"rn_no_{cid}"):
                        st.session_state[f"renaming_{cid}"] = False
                        st.rerun()

        st.markdown("---")

        # ===== 预设模板 =====
        with st.expander("快速创建", expanded=False):
            presets = {
                "代码审查专家": ("ReAct Agent", "你是代码审查专家。审查代码的安全漏洞、代码质量和性能问题，给出严重程度评级和修复建议。"),
                "Python 开发者": ("Coder", "你是 Python 开发专家。编写高质量、符合 PEP8 的代码，注重可读性和性能。"),
                "技术文档写手": ("Summarizer", "你是技术文档专家。将复杂的技术内容转化为清晰、简洁的文档和教程。"),
                "数据分析助手": ("Researcher", "你是数据分析专家。分析数据趋势、生成洞察报告、提供数据驱动的建议。"),
                "全栈工程师": ("ReAct Agent", "你是全栈工程师。精通前后端开发、数据库设计、API 开发和系统架构。"),
            }
            for name, (atype, prompt) in presets.items():
                if st.button(f"{name}", key=f"preset_{name}", use_container_width=True):
                    agent = create_agent(atype, name, prompt)
                    st.success(f"{agent.name} 已创建")
                    st.rerun()

        st.markdown("---")

        # ===== Agent 管理 =====
        with st.expander("创建 Agent", expanded=True):
            agent_type = st.selectbox("类型", ["ReAct Agent", "Planner", "Researcher", "Coder", "Reviewer", "Summarizer"])
            agent_name = st.text_input("名称", f"{agent_type}_{len(st.session_state.agents)+1}")
            system_prompt = st.text_area("系统提示", placeholder="定义 Agent 角色...", height=60)
            if st.button("创建", use_container_width=True, type="primary"):
                agent = create_agent(agent_type, agent_name, system_prompt)
                st.success(f"{agent.name} 已创建")
                st.rerun()

        # Agent 列表（带删除）
        if st.session_state.agents:
            st.markdown("#### 已创建")
            for aid, agent in list(st.session_state.agents.items()):
                status_class = f"status-{agent.state.status.value}"
                c_info, c_del_a = st.columns([5, 1])
                with c_info:
                    st.markdown(f"""
                    <div class="agent-card">
                        <div>
                            <div class="agent-name">{agent.name}</div>
                            <div class="agent-type">{type(agent).__name__}</div>
                        </div>
                        <span class="agent-status {status_class}">{agent.state.status.value}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with c_del_a:
                    if st.button("x", key=f"del_ag_{aid}", help="删除"):
                        del st.session_state.agents[aid]
                        st.rerun()

        st.markdown("---")

        # ===== 设置折叠 =====
        with st.expander("API 设置"):
            import os
            env_key = os.environ.get("LLM_API_KEY", "")
            env_provider = os.environ.get("LLM_PROVIDER", "mimo")

            quick_provider = st.selectbox(
                "提供商",
                ["mimo", "openai", "anthropic", "local"],
                index=["mimo", "openai", "anthropic", "local"].index(env_provider) if env_provider in ["mimo", "openai", "anthropic", "local"] else 0,
                key="sidebar_provider",
            )
            if quick_provider == "mimo":
                quick_key = st.text_input("API Key", value=env_key, type="password", key="sidebar_mimo_key")
                if quick_key:
                    st.session_state["settings_provider"] = "mimo"
                    st.session_state["settings_mimo_key"] = quick_key
                    st.session_state.setdefault("settings_model", "mimo-v2.5-pro")
            elif quick_provider == "openai":
                quick_key = st.text_input("API Key", type="password", key="sidebar_openai_key")
                if quick_key:
                    st.session_state["settings_provider"] = "openai"
                    st.session_state["settings_openai_key"] = quick_key
                    st.session_state.setdefault("settings_model", "gpt-4o-mini")
            elif quick_provider == "anthropic":
                quick_key = st.text_input("API Key", type="password", key="sidebar_anthropic_key")
                if quick_key:
                    st.session_state["settings_provider"] = "anthropic"
                    st.session_state["settings_anthropic_key"] = quick_key
                    st.session_state.setdefault("settings_model", "claude-sonnet-4-20250514")
            else:
                st.session_state["settings_provider"] = "local"
                st.caption("需本地运行 Ollama")

            # API 状态
            provider = st.session_state.get("settings_provider", "")
            if provider == "mimo":
                key = st.session_state.get("settings_mimo_key", "") or env_key
                if key: st.success("MiMo 已连接")
                else: st.warning("未配置")
            elif provider == "openai":
                key = st.session_state.get("settings_openai_key", "") or env_key
                if key: st.success("OpenAI 已连接")
                else: st.warning("未配置")
            elif provider == "anthropic":
                key = st.session_state.get("settings_anthropic_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
                if key: st.success("Anthropic 已连接")
                else: st.warning("未配置")
            else:
                st.info("本地模型模式")

        with st.expander("文档知识库"):
            uploaded_files = st.file_uploader(
                "上传文档",
                type=["txt", "md", "py", "json", "csv"],
                accept_multiple_files=True,
            )
            if uploaded_files:
                from agentflow.tools.base import DocumentRetrievalTool
                doc_tool = None
                for agent in st.session_state.agents.values():
                    if hasattr(agent, "tools") and agent.tools:
                        doc_tool = agent.tools.get("document_retrieval")
                        if doc_tool: break
                if doc_tool is None:
                    doc_tool = DocumentRetrievalTool()
                total_chunks = 0
                for uf in uploaded_files:
                    content = uf.read().decode("utf-8", errors="ignore")
                    chunks = doc_tool.load_text(content, source=uf.name)
                    total_chunks += chunks
                st.caption(f"{len(uploaded_files)} 文件 / {total_chunks} 片段")

        with st.expander("编排策略"):
            strategy = st.selectbox(
                "策略",
                ["sequential", "parallel", "debate", "supervisor"],
                format_func=lambda x: {"sequential": "串行", "parallel": "并行", "debate": "辩论", "supervisor": "主管"}[x],
                key="strategy",
            )


# ============ 对话页面 ============
def chat_page():
    chat = get_current_chat()
    messages = chat["messages"]

    col1, col2 = st.columns([2, 1])

    with col1:
        # 导出按钮
        if messages:
            md_lines = [f"# {chat['name']}\n"]
            for msg in messages:
                role = "用户" if msg["role"] == "user" else "Agent"
                md_lines.append(f"## {role}\n\n{msg['content']}\n")
            md_content = "\n".join(md_lines)
            st.download_button("导出 Markdown", md_content, file_name=f"{chat['name']}.md", mime="text/markdown")

        st.markdown("### 对话")

        # 新手引导
        if not messages:
            st.info("👋 欢迎使用 AgentFlow！\n\n1. 在左侧创建一个 Agent\n2. 在下方输入框输入任务\n3. 开始对话")

        # 聊天历史
        chat_container = st.container(height=400)
        with chat_container:
            for msg in messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if "steps" in msg:
                        with st.expander("执行过程"):
                            for step in msg["steps"]:
                                st.caption(step)
                    if "metadata" in msg:
                        with st.expander("执行详情"):
                            st.json(msg["metadata"])

        # 输入
        if prompt := st.chat_input("输入你的任务..."):
            messages.append({"role": "user", "content": prompt})
            st.session_state.total_messages += 1

            # 自动命名对话（取前10个字）
            if chat["name"] == "新对话" and len(messages) == 1:
                chat["name"] = prompt[:15] + ("..." if len(prompt) > 15 else "")

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            agents = list(st.session_state.agents.values())
            if not agents:
                st.warning("⚠️ 请先在左侧创建至少一个Agent")
                return

            with chat_container:
                with st.chat_message("assistant"):
                    strategy = st.session_state.get("strategy", "sequential")
                    start_time = time.perf_counter()
                    steps: list[str] = []

                    # 状态提示
                    status_placeholder = st.empty()
                    status_placeholder.caption("连接中...")

                    try:
                        # 单Agent模式：流式输出
                        if len(agents) == 1 and strategy == "sequential":
                            agent = agents[0]
                            steps.append(f"[{agent.name}] 开始思考...")
                            status_placeholder.caption(f"[{agent.name}] 思考中...")

                            # 记录执行前的消息数
                            msgs_before = len(agent.conversation)

                            async def _stream_gen():
                                async for chunk in agent.stream_chat(prompt):
                                    yield chunk

                            loop = asyncio.new_event_loop()
                            full_text = st.write_stream(loop.run_until_complete(_stream_gen()))
                            status_placeholder.empty()
                            duration = (time.perf_counter() - start_time) * 1000

                            # 提取工具调用信息
                            new_msgs = agent.conversation.messages[msgs_before:]
                            for m in new_msgs:
                                if hasattr(m, 'role') and m.role.value == 'tool':
                                    tool_name = m.name or "unknown"
                                    result_preview = m.content[:80] + ("..." if len(m.content) > 80 else "")
                                    steps.append(f"  工具调用: {tool_name} → {result_preview}")

                            steps.append(f"完成 ({duration:.0f}ms)")
                            messages.append({
                                "role": "assistant",
                                "content": full_text,
                                "steps": steps,
                                "metadata": {"strategy": "stream", "duration_ms": round(duration, 1)},
                            })
                            st.session_state.execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "task": prompt[:100],
                                "strategy": "stream",
                                "duration_ms": round(duration, 1),
                                "status": "success",
                            })

                        # 多Agent模式：流式编排
                        else:
                            steps.append(f"策略: {strategy} | Agent数: {len(agents)}")
                            for a in agents:
                                steps.append(f"  {a.name} ({type(a).__name__})")

                            orchestrator = st.session_state.orchestrator
                            orchestrator.strategy = OrchestrationStrategy(strategy)

                            async def _orch_stream():
                                async for chunk in orchestrator.run_stream(prompt, [a.id for a in agents]):
                                    yield chunk

                            loop = asyncio.new_event_loop()
                            full_text = st.write_stream(loop.run_until_complete(_orch_stream()))
                            duration = (time.perf_counter() - start_time) * 1000

                            steps.append(f"完成 ({duration:.0f}ms)")
                            metadata = {
                                "strategy": strategy,
                                "duration_ms": round(duration, 1),
                                "agents_used": len(agents),
                            }
                            messages.append({
                                "role": "assistant",
                                "content": full_text,
                                "steps": steps,
                                "metadata": metadata,
                            })
                            st.session_state.execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "task": prompt[:100],
                                "strategy": strategy,
                                "duration_ms": round(duration, 1),
                                "status": "success",
                            })

                        st.session_state.total_messages += 1
                        _save_conversations()

                    except Exception as e:
                        st.error(f"执行错误: {e}")
                        steps.append(f"错误: {e}")
                        messages.append({
                            "role": "assistant",
                            "content": f"执行出错: {e}",
                            "steps": steps,
                        })
                        if st.button("重试", key=f"retry_{len(messages)}"):
                            messages.pop()  # 移除错误消息
                            st.rerun()
                        st.session_state.execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "task": prompt[:100],
                            "strategy": strategy,
                            "status": "error",
                            "error": str(e),
                        })
                        _save_conversations()

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
                ms = log.get("duration_ms", 0)
                st.caption(f"{icon} {log['task']} ({ms}ms)")
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
                with st.expander(f"📋 {wf.name} — {wf.description}"):
                    st.json(wf.to_dict())
                    exec_key = f"exec_wf_{wf_id}"
                    task_input = st.text_input("输入任务", key=f"task_{wf_id}", placeholder="描述工作流要处理的任务...")
                    if st.button("▶️ 执行工作流", key=exec_key, type="primary"):
                        if not task_input:
                            st.warning("请输入任务描述")
                        else:
                            with st.spinner("工作流执行中..."):
                                try:
                                    loop = asyncio.new_event_loop()
                                    result = loop.run_until_complete(
                                        st.session_state.workflow_engine.execute(wf, {"task": task_input})
                                    )
                                    if result.status == "completed":
                                        st.success("✅ 执行完成")
                                    else:
                                        st.error(f"❌ 执行失败: {result.status}")
                                    st.json({k: v.model_dump() if hasattr(v, 'model_dump') else str(v) for k, v in result.node_results.items()})
                                except Exception as e:
                                    st.error(f"❌ {e}")
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
    from agentflow.workflow.engine import WorkflowBuilder

    # 先创建并注册所需的 Agent
    needed = {
        "Planner": "分析用户意图，决定路由到哪个处理模块",
        "ReAct Agent": "处理订单相关的客户问题",
        "Coder": "处理技术支持和代码相关问题",
        "Researcher": "处理销售咨询和产品信息查询",
        "Summarizer": "整合各模块的处理结果，生成最终回复",
    }
    for agent_type, prompt in needed.items():
        existing = [a for a in st.session_state.agents.values() if type(a).__name__ == agent_type.replace(" ", "")]
        if not existing:
            create_agent(agent_type, agent_type, prompt)

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
    from agentflow.workflow.engine import WorkflowBuilder

    needed = {
        "Reviewer": "审查代码质量、安全漏洞和性能问题",
        "Summarizer": "整合多维度审查结果，生成综合报告",
    }
    for agent_type, prompt in needed.items():
        existing = [a for a in st.session_state.agents.values() if type(a).__name__ == agent_type]
        if not existing:
            create_agent(agent_type, agent_type, prompt)

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
    from agentflow.workflow.engine import WorkflowBuilder

    needed = {
        "Planner": "制定数据分析计划",
        "Coder": "执行数据分析代码",
        "Summarizer": "生成分析报告",
    }
    for agent_type, prompt in needed.items():
        existing = [a for a in st.session_state.agents.values() if type(a).__name__ == agent_type]
        if not existing:
            create_agent(agent_type, agent_type, prompt)

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
    st.markdown("### 监控面板")

    # 自动刷新
    col_title, col_refresh = st.columns([5, 1])
    with col_refresh:
        if st.button("刷新", use_container_width=True):
            st.rerun()
    auto_refresh = st.checkbox("自动刷新 (5秒)", key="auto_refresh")

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
        total_tok = sum(total_tokens.values())
        st.markdown(f"""
        <div class="metric-card orange">
            <div class="label">总Token</div>
            <div class="value">{total_tok:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        # 估算成本（按 GPT-4o-mini 价格 $0.15/1M input, $0.6/1M output）
        estimated_cost = total_tok * 0.0000003  # 粗略估算
        st.markdown(f"""
        <div class="metric-card blue">
            <div class="label">估算成本</div>
            <div class="value">${estimated_cost:.4f}</div>
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
                try:
                    import pandas as pd
                    df = pd.DataFrame(st.session_state.execution_log)
                    if "duration_ms" in df.columns:
                        st.line_chart(df["duration_ms"])
                except ImportError:
                    st.info("安装 plotly 和 pandas 以查看图表: pip install plotly pandas")
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

    # 自动刷新
    if st.session_state.get("auto_refresh"):
        time.sleep(5)
        st.rerun()


# ============ 主函数 ============
def main():
    init_session_state()
    render_top_nav()
    render_sidebar()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💬 对话", "🔧 工作流", "📊 监控", "🧪 评估", "🔌 插件", "⚙️ 设置"
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
    with tab6:
        from agentflow.ui.pages.settings_page import render_settings_page
        render_settings_page()


if __name__ == "__main__":
    main()
