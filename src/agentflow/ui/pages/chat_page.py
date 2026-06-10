"""对话页面"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import streamlit as st


def _save_conversations() -> None:
    """持久化对话历史到文件。"""
    import json, os
    path = "data/conversations.json"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_data = {}
        for cid, conv in st.session_state.conversations.items():
            save_data[cid] = {"name": conv["name"], "messages": conv["messages"]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def render():
    """渲染对话页面。"""
    cid = st.session_state.current_conversation_id
    chat = st.session_state.conversations[cid]
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
            st.info("欢迎使用 AgentFlow！\n\n1. 在左侧创建一个 Agent\n2. 在下方输入框输入任务\n3. 开始对话")

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

            # 自动命名对话（取前15个字）
            if chat["name"] == "新对话" and len(messages) == 1:
                chat["name"] = prompt[:15] + ("..." if len(prompt) > 15 else "")

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            agents = list(st.session_state.agents.values())
            if not agents:
                st.warning("请先在左侧创建至少一个Agent")
                return

            with chat_container:
                with st.chat_message("assistant"):
                    strategy = st.session_state.get("strategy", "sequential")
                    start_time = time.perf_counter()
                    steps: list[str] = []

                    status_placeholder = st.empty()
                    status_placeholder.caption("连接中...")

                    try:
                        # 单Agent模式：流式输出
                        if len(agents) == 1 and strategy == "sequential":
                            agent = agents[0]
                            steps.append(f"[{agent.name}] 开始思考...")
                            status_placeholder.caption(f"[{agent.name}] 思考中...")

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
                                if hasattr(m, "role") and m.role.value == "tool":
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
                            from agentflow.workflow.orchestrator import OrchestrationStrategy

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
                            messages.append({
                                "role": "assistant",
                                "content": full_text,
                                "steps": steps,
                                "metadata": {"strategy": strategy, "duration_ms": round(duration, 1), "agents_used": len(agents)},
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
                        messages.append({"role": "assistant", "content": f"执行出错: {e}", "steps": steps})
                        if st.button("重试", key=f"retry_{len(messages)}"):
                            messages.pop()
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
        st.markdown("### 实时状态")

        agents = list(st.session_state.agents.values())
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

        st.markdown("#### 最近执行")
        if st.session_state.execution_log:
            for log in st.session_state.execution_log[-5:][::-1]:
                icon = "+" if log["status"] == "success" else "-"
                ms = log.get("duration_ms", 0)
                st.caption(f"{icon} {log['task']} ({ms}ms)")
        else:
            st.caption("暂无执行记录")
