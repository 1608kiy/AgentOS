"""监控面板页面"""

from __future__ import annotations

import time

import streamlit as st


def render():
    """渲染监控面板页面。"""
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
        estimated_cost = total_tok * 0.0000003
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
        st.markdown("#### Agent Token用量")
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
        st.markdown("#### 执行历史")
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
        st.markdown("#### 执行状态分布")
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
    st.markdown("#### Agent 状态详情")

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
