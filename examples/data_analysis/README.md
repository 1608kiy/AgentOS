# 数据分析流水线

五个专业 Agent 按顺序协作，从需求理解到最终报告，完成端到端的数据分析流程。

## Agent 与编排策略

- AnalysisPlanner (ReActAgent) -- 理解需求、制定分析计划
- DataExtractor (ReActAgent) -- 数据提取与清洗
- DataAnalyst (ReActAgent) -- 统计分析与洞察发现
- Visualizer (ReActAgent) -- 图表选型与可视化方案
- ReportGenerator (ReActAgent) -- 整合结果、生成报告
- 编排策略: Sequential（五个 Agent 按顺序串行执行，上一个的输出作为下一个的上下文）

## 运行

```bash
# 前提: 在项目根目录的 .env 中配置 LLM API Key
python examples/data_analysis/main.py
```

## 预期输出

针对电商平台用户购买行为的分析需求，依次经历规划、提取、分析、可视化、报告五个阶段，最终输出完整的数据分析报告。
