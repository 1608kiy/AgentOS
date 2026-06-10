"""工作流设计器页面"""

from __future__ import annotations

import asyncio

import streamlit as st

from agentflow.workflow.engine import WorkflowBuilder


def render():
    """渲染工作流设计器页面。"""
    st.markdown("### 工作流设计器")

    tab1, tab2, tab3 = st.tabs(["可视化设计", "模板库", "JSON定义"])

    with tab1:
        from agentflow.ui.components.workflow_designer import render_workflow_designer
        st.caption("双击节点编辑 | Shift+拖拽连线 | 拖拽移动节点")
        render_workflow_designer(height=500)

    with tab2:
        st.markdown("#### 工作流模板")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""<div class="agent-card"><div class="agent-name">智能客服</div><div class="agent-type">意图识别 → 路由 → 处理 → 总结</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_cs"):
                _create_customer_service_workflow()
        with col2:
            st.markdown("""<div class="agent-card"><div class="agent-name">代码审查</div><div class="agent-type">安全 → 质量 → 性能 → 评审</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_cr"):
                _create_code_review_workflow()
        with col3:
            st.markdown("""<div class="agent-card"><div class="agent-name">数据分析</div><div class="agent-type">规划 → 分析 → 报告</div></div>""", unsafe_allow_html=True)
            if st.button("使用此模板", key="tpl_da"):
                _create_data_analysis_workflow()

        st.markdown("---")
        st.markdown("#### 已创建工作流")
        if st.session_state.workflows:
            for wf_id, wf in st.session_state.workflows.items():
                with st.expander(f"{wf.name} — {wf.description}"):
                    st.json(wf.to_dict())
                    task_input = st.text_input("输入任务", key=f"task_{wf_id}", placeholder="描述工作流要处理的任务...")
                    if st.button("执行工作流", key=f"exec_wf_{wf_id}", type="primary"):
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
                                        st.success("执行完成")
                                    else:
                                        st.error(f"执行失败: {result.status}")
                                    st.json({k: v.model_dump() if hasattr(v, "model_dump") else str(v) for k, v in result.node_results.items()})
                                except Exception as e:
                                    st.error(f"{e}")
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
                st.success("解析成功")
            except Exception as e:
                st.error(f"JSON解析错误: {e}")


def _create_agent_if_needed(agent_type: str, name: str, prompt: str) -> None:
    """如不存在则创建 Agent 并注册到工作流引擎。"""
    existing = [a for a in st.session_state.agents.values() if type(a).__name__ == agent_type.replace(" ", "")]
    if not existing:
        from agentflow.ui.app import create_agent
        create_agent(agent_type, name, prompt)


def _create_customer_service_workflow():
    needed = {
        "Planner": "分析用户意图，决定路由到哪个处理模块",
        "ReActAgent": "处理订单相关的客户问题",
        "Coder": "处理技术支持和代码相关问题",
        "Researcher": "处理销售咨询和产品信息查询",
        "Summarizer": "整合各模块的处理结果，生成最终回复",
    }
    for agent_type, prompt in needed.items():
        _create_agent_if_needed(agent_type, agent_type, prompt)

    builder = WorkflowBuilder("智能客服", "用户咨询 → 意图识别 → 专业处理 → 总结")
    builder.add_agent_node("意图识别", "Planner", "分析用户意图")
    builder.add_agent_node("订单处理", "ReActAgent", "处理订单问题")
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
    for agent_type, prompt in {
        "Reviewer": "审查代码质量、安全漏洞和性能问题",
        "Summarizer": "整合多维度审查结果，生成综合报告",
    }.items():
        _create_agent_if_needed(agent_type, agent_type, prompt)

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
    for agent_type, prompt in {
        "Planner": "制定数据分析计划",
        "Coder": "执行数据分析代码",
        "Summarizer": "生成分析报告",
    }.items():
        _create_agent_if_needed(agent_type, agent_type, prompt)

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
