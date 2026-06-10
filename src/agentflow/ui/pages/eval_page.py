"""评估面板页面"""

from __future__ import annotations

import asyncio

import streamlit as st

from agentflow.core.evaluation import (
    EvalRunner,
    EvalTask,
    ContainsScorer,
    ExactMatchScorer,
    CompositeScorer,
    LLMScorer,
    BENCHMARK_TASKS,
    create_eval_suite,
)


def render_eval_page():
    st.markdown("### Agent 评估")

    tab1, tab2, tab3 = st.tabs(["运行评估", "基准测试集", "历史报告"])

    with tab1:
        _render_run_eval()

    with tab2:
        _render_benchmark()

    with tab3:
        _render_history()


def _render_run_eval():
    agents = st.session_state.get("agents", {})
    if not agents:
        st.warning("请先创建至少一个Agent")
        return

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 评估配置")

        agent_id = st.selectbox(
            "选择Agent",
            options=list(agents.keys()),
            format_func=lambda x: agents[x].name,
        )

        suite_name = st.selectbox(
            "测试集",
            ["general", "coding", "reasoning", "自定义"],
        )

        scorer_type = st.selectbox(
            "评分方式",
            ["包含匹配", "精确匹配", "组合评分", "LLM评分"],
        )

        parallel = st.checkbox("并行执行", value=False)

        if st.button("开始评估", use_container_width=True, type="primary"):
            agent = agents[agent_id]

            if suite_name == "自定义":
                custom_input = st.text_area("自定义任务（每行一个）", height=100)
                tasks = [
                    EvalTask(name=f"custom_{i}", input=line.strip())
                    for i, line in enumerate(custom_input.split("\n"))
                    if line.strip()
                ]
            else:
                tasks = create_eval_suite(suite_name)

            scorer_map = {
                "包含匹配": ContainsScorer(),
                "精确匹配": ExactMatchScorer(),
                "组合评分": CompositeScorer([(ContainsScorer(), 0.6), (ExactMatchScorer(), 0.4)]),
                "LLM评分": LLMScorer(),
            }
            scorer = scorer_map.get(scorer_type, ContainsScorer())

            runner = EvalRunner(agent=agent, scorer=scorer, parallel=parallel)

            with st.spinner(f"正在评估 {len(tasks)} 个任务..."):
                loop = asyncio.new_event_loop()
                report = loop.run_until_complete(runner.run_suite(tasks))

            st.session_state.eval_report = report
            st.success(f"评估完成! 通过率: {report.pass_rate:.0%}")

    with col2:
        st.markdown("#### 评估结果")
        report = st.session_state.get("eval_report")
        if report:
            _render_report(report)
        else:
            st.info("请运行评估以查看结果")


def _render_report(report):
    import pandas as pd

    # 概览指标
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总任务", report.total_tasks)
    c2.metric("通过", report.passed)
    c3.metric("通过率", f"{report.pass_rate:.0%}")
    c4.metric("平均分", f"{report.avg_score:.2f}")

    c1, c2 = st.columns(2)
    c1.metric("平均耗时", f"{report.avg_duration_ms:.0f}ms")
    c2.metric("总Token", f"{report.total_tokens:,}")

    st.markdown("---")

    # 详细结果
    st.markdown("#### 详细结果")
    df = pd.DataFrame([
        {
            "任务": r.task_name,
                "通过": "Y" if r.passed else "N",
            "分数": f"{r.score:.2f}",
            "耗时(ms)": f"{r.duration_ms:.0f}",
            "迭代": r.iterations,
        }
        for r in report.results
    ])
    st.dataframe(df, use_container_width=True)

    # 分数分布
    st.markdown("#### 分数分布")
    scores = [r.score for r in report.results]
    score_df = pd.DataFrame({"分数": scores})
    st.bar_chart(score_df)


def _render_benchmark():
    st.markdown("#### 基准测试集")

    for suite_name, tasks in BENCHMARK_TASKS.items():
        with st.expander(f"{suite_name} ({len(tasks)}个任务)"):
            for task in tasks:
                st.markdown(f"**{task.name}**")
                st.caption(f"输入: {task.input}")
                if task.expected_contains:
                    st.caption(f"期望包含: {', '.join(task.expected_contains)}")


def _render_history():
    st.markdown("#### 历史评估报告")
    report = st.session_state.get("eval_report")
    if report:
        st.json(report.model_dump())
    else:
        st.info("暂无评估记录")
