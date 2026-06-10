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
    page_icon="A",
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
# 已拆分到 pages/chat_page.py

# ============ 工作流设计器页面 ============
# 已拆分到 pages/workflow_page.py

# ============ 监控面板页面 ============
# 已拆分到 pages/monitor_page.py


# ============ 主函数 ============
def main():
    init_session_state()
    render_top_nav()
    render_sidebar()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "对话", "工作流", "监控", "评估", "插件", "设置"
    ])

    with tab1:
        from agentflow.ui.pages.chat_page import render as render_chat
        render_chat()
    with tab2:
        from agentflow.ui.pages.workflow_page import render as render_workflow
        render_workflow()
    with tab3:
        from agentflow.ui.pages.monitor_page import render as render_monitor
        render_monitor()
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
