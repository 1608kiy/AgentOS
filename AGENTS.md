# AgentFlow

Enterprise multi-agent collaboration platform. Python 3.11+, FastAPI + Streamlit, src-layout.

## Commands

```bash
# Install (dev = full + test tools)
pip install -e ".[dev]"

# Test — pytest-asyncio auto mode, all async tests run automatically
pytest tests/ -v
pytest tests/ -v --cov=agentflow --cov-report=term-missing

# Lint & format (CI runs both)
ruff check src/ tests/
ruff format --check src/ tests/
ruff format src/ tests/          # auto-fix

# Type check
mypy src/

# CLI entrypoints
agentflow run "task"             # run agent task
agentflow serve                  # FastAPI on :8000
agentflow ui                     # Streamlit on :8501
```

CI pipeline: `lint → test (3.11 + 3.12) → build → docker`. Lint must pass before tests run.

## Layout

```
src/agentflow/
├── cli.py              # typer CLI (agentflow command)
├── core/               # config, llm, message, state, logging, evaluation, plugins, session, otel
├── agents/base.py      # ReAct agent + 5 built-in types (Planner/Researcher/Coder/Reviewer/Summarizer)
├── tools/base.py       # Tool ABC, ToolRegistry, sandboxed CodeExecutorTool
├── memory/manager.py   # layered memory (short-term/long-term/working)
├── workflow/
│   ├── engine.py       # DAG workflow engine (5 node types)
│   └── orchestrator.py # multi-agent orchestration (sequential/parallel/debate/supervisor)
├── api/                # FastAPI app, JWT+APIKey auth, WebSocket streaming
├── ui/                 # Streamlit UI, canvas workflow designer
└── utils/              # structured output parsing
tests/
├── conftest.py         # shared fixtures: config, mock_llm_config
├── unit/               # one test file per module
└── integration/test_api.py  # httpx ASGITransport end-to-end tests
```

## Key conventions

- **src layout**: package root is `src/agentflow`, wheel packages from `src/` via hatchling.
- **Config via env**: `AgentFlowConfig` uses pydantic-settings with env prefixes (`LLM_`, `DATABASE_`, `REDIS_`, `API_`, `LOG_`, `VECTOR_`, `AGENT_`). Copy `.env.example` to `.env`.
- **Async tests auto-run**: `asyncio_mode = "auto"` in pytest config — write `async def test_*` directly, no decorator needed. CI uses `pytest-asyncio>=0.24`.
- **MockLLMClient for tests**: `from agentflow.core.llm import MockLLMClient` — inject with `agent.llm = MockLLMClient()` to avoid real API calls.
- **No LangChain dependency**: all core engine logic is self-implemented (ReAct loop, DAG executor, orchestrator).
- **Auth**: JWT via `/api/v1/auth/token` (admin/admin for dev). Protected endpoints use `Depends(get_current_user)`. Admin-only uses `Depends(require_admin)`.
- **Middleware pipeline**: agents have `before_run` / `after_run` / `on_error` hooks. Built-in: `ContentFilterMiddleware`, `CostTrackerMiddleware`.
- **LLM retry**: exponential backoff on 429/500/502/503, LRU response cache.
- **Ruff rules**: `select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]`, line-length 100, target Python 3.11.
- **mypy strict**: enabled for all of `src/`.
- **Docker**: multi-stage build, non-root user, health check at `/api/v1/health`. `PYTHONPATH=/app/src` is set in container.
- **Data dirs**: `data/` (SQLite, Chroma) are gitignored. Create them at runtime.

## Gotchas

- `AgentConfig` in `agents/base.py` is a Pydantic BaseModel, distinct from `core.config.AgentFlowConfig` (pydantic-settings). Don't confuse the two.
- The CLI `ui` command runs `streamlit run src/agentflow/ui/app.py` — it expects to be run from the repo root.
- Integration tests use `httpx.ASGITransport(app=app)` to test FastAPI without a running server.
- Version in `__init__.py` (0.1.0) and `pyproject.toml` (0.2.0) are out of sync — trust `pyproject.toml` as source of truth.
