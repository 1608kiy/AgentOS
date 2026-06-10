# 代码审查助手

通过多 Agent 协作完成代码的安全性、质量和性能三维审查，最终由综合评审 Agent 汇总报告。

## Agent 与编排策略

- SecurityScanner (ReActAgent) -- 安全漏洞扫描
- QualityChecker (ReActAgent) -- 代码质量检查
- PerformanceAnalyzer (ReActAgent) -- 性能瓶颈分析
- CodeReviewer (ReActAgent) -- 综合评审汇总
- 编排策略: Parallel（三个审查 Agent 并行执行，结果交由 Reviewer 汇总）

## 运行

```bash
# 前提: 在项目根目录的 .env 中配置 LLM API Key
python examples/code_review/main.py
```

## 预期输出

依次输出待审查的示例代码（含 eval 和 SQL 注入），随后输出由四个 Agent 协作生成的综合审查报告，包括安全问题、质量缺陷、性能隐患及修复建议。
