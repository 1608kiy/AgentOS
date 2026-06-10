"""工具系统 - 可扩展的工具注册与调用"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_function_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class Tool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'name') or not cls.name:
            cls.name = cls.__name__.lower().replace('tool', '')

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        ...

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def to_function_schema(self) -> dict[str, Any]:
        return self.to_definition().to_function_schema()


class ToolRegistry:
    """工具注册中心"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: list[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return [tool.to_definition() for tool in self._tools.values()]

    def to_function_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_function_schema() for tool in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    def remove(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def clear(self) -> None:
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ============ 内置工具 ============


class CalculatorTool(Tool):
    """计算器工具 - 安全版"""
    name = "calculator"
    description = "执行数学计算。支持基本运算和数学函数。"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2 + 3 * 4' 或 'sqrt(16)'",
            }
        },
        "required": ["expression"],
    }

    # 白名单：只允许这些名称出现在表达式中
    _SAFE_NAMES: dict[str, Any] = {}

    def __init__(self) -> None:
        import math
        self._SAFE_NAMES = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "log10": math.log10,
            "exp": math.exp, "pi": math.pi, "e": math.e,
            "ceil": math.ceil, "floor": math.floor,
        }

    async def execute(self, expression: str = "", **kwargs: Any) -> str:
        try:
            # 预检查：拒绝包含危险模式的表达式
            dangerous = ["import", "exec", "eval", "__", "open", "os.", "sys.", "subprocess"]
            for pattern in dangerous:
                if pattern in expression.lower():
                    return f"安全拒绝: 表达式包含禁止的模式 '{pattern}'"

            result = eval(expression, {"__builtins__": {}}, self._SAFE_NAMES)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"


class WebSearchTool(Tool):
    """网络搜索工具 - 真实API版"""
    name = "web_search"
    description = "搜索网络获取信息。支持Tavily/SerpAPI/DuckDuckGo。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        self._tavily_key = os.getenv("TAVILY_API_KEY", "")
        self._serpapi_key = os.getenv("SERPAPI_API_KEY", "")

    async def execute(self, query: str = "", num_results: int = 5, **kwargs: Any) -> str:
        # 优先使用Tavily
        if self._tavily_key:
            return await self._search_tavily(query, num_results)
        # 其次使用SerpAPI
        if self._serpapi_key:
            return await self._search_serpapi(query, num_results)
        # 兜底：使用DuckDuckGo（无需API key）
        return await self._search_duckduckgo(query, num_results)

    async def _search_tavily(self, query: str, num_results: int) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self._tavily_key,
                        "query": query,
                        "max_results": num_results,
                    },
                    timeout=15.0,
                )
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return f"未找到 '{query}' 的相关结果"

                lines = [f"搜索结果 (查询: '{query}'):"]
                for i, r in enumerate(results[:num_results], 1):
                    title = r.get("title", "")
                    snippet = r.get("content", "")[:200]
                    url = r.get("url", "")
                    lines.append(f"{i}. {title}\n   {snippet}\n   来源: {url}")
                return "\n".join(lines)
        except Exception as e:
            return f"Tavily搜索错误: {e}"

    async def _search_serpapi(self, query: str, num_results: int) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": self._serpapi_key,
                        "num": num_results,
                        "engine": "google",
                    },
                    timeout=15.0,
                )
                data = resp.json()
                organic = data.get("organic_results", [])
                if not organic:
                    return f"未找到 '{query}' 的相关结果"

                lines = [f"搜索结果 (查询: '{query}'):"]
                for i, r in enumerate(organic[:num_results], 1):
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")[:200]
                    link = r.get("link", "")
                    lines.append(f"{i}. {title}\n   {snippet}\n   来源: {link}")
                return "\n".join(lines)
        except Exception as e:
            return f"SerpAPI搜索错误: {e}"

    async def _search_duckduckgo(self, query: str, num_results: int) -> str:
        """DuckDuckGo搜索（无需API key）"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1"},
                    headers={"User-Agent": "AgentFlow/0.1"},
                    timeout=15.0,
                )
                data = resp.json()
                results = data.get("RelatedTopics", [])
                if not results:
                    return f"未找到 '{query}' 的相关结果（DuckDuckGo）"

                lines = [f"搜索结果 (查询: '{query}'):"]
                count = 0
                for r in results:
                    if count >= num_results:
                        break
                    text = r.get("Text", "")
                    url = r.get("FirstURL", "")
                    if text:
                        count += 1
                        lines.append(f"{count}. {text[:200]}\n   来源: {url}")
                return "\n".join(lines) if count > 0 else f"未找到 '{query}' 的相关结果"
        except Exception as e:
            return f"DuckDuckGo搜索错误: {e}"


class FileReaderTool(Tool):
    """文件读取工具"""
    name = "file_reader"
    description = "读取文件内容。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "文件路径"},
            "max_size": {"type": "integer", "description": "最大读取字节数", "default": 100000},
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str = "", max_size: int = 100000, **kwargs: Any) -> str:
        try:
            path = Path(file_path)
            if not path.exists():
                return f"文件不存在: {file_path}"
            if not path.is_file():
                return f"不是文件: {file_path}"
            if path.stat().st_size > max_size:
                return f"文件过大 ({path.stat().st_size} bytes)，超过限制 ({max_size} bytes)"
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取文件错误: {e}"


class FileWriterTool(Tool):
    """文件写入工具"""
    name = "file_writer"
    description = "写入文件内容。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, file_path: str = "", content: str = "", **kwargs: Any) -> str:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"文件已写入: {file_path} ({len(content)} 字符)"
        except Exception as e:
            return f"写入文件错误: {e}"


class CodeExecutorTool(Tool):
    """代码执行工具 - 沙箱版（AST静态检查 + subprocess隔离 + 超时 + 干净env）

    安全策略（纵深防御）：
    1. AST 静态分析：拒绝 import 危险模块、调用危险内置函数、访问 dunder 属性，
       从语法层面拦截，避免旧版「子串黑名单」既能被绕过（如 ``getattr(__builtins__, ...)``）
       又会误伤（如变量名里含 "open"）的问题。
    2. subprocess 隔离 + 空环境变量 + 超时，限制副作用与失控执行。

    注意：这是「降低风险」而非「绝对安全」的沙箱。真正不可信代码应在容器/gVisor/
    nsjail 等 OS 级隔离中运行（详见 README 安全说明）。
    """
    name = "code_executor"
    description = "在沙箱中执行Python代码并返回结果。有超时和安全限制。"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python代码"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 10},
        },
        "required": ["code"],
    }

    # 禁止导入的模块（含子模块前缀匹配）
    _BLOCKED_MODULES = frozenset([
        "os", "sys", "subprocess", "shutil", "socket", "ctypes",
        "importlib", "pickle", "marshal", "multiprocessing", "threading",
        "pty", "fcntl", "signal", "resource", "mmap",
    ])
    # 禁止调用的内置函数
    _BLOCKED_CALLS = frozenset([
        "eval", "exec", "compile", "open", "input",
        "__import__", "globals", "locals", "vars", "getattr",
        "setattr", "delattr", "memoryview", "breakpoint",
    ])

    def _check_ast(self, code: str) -> str | None:
        """AST 静态检查。返回错误信息表示拒绝，None 表示通过。"""
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"语法错误: {e}"

        for node in ast.walk(tree):
            # 拒绝危险 import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in self._BLOCKED_MODULES:
                        return f"安全拒绝: 禁止导入模块 '{alias.name}'"
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top in self._BLOCKED_MODULES:
                    return f"安全拒绝: 禁止从模块 '{node.module}' 导入"
            # 拒绝危险内置调用
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in self._BLOCKED_CALLS:
                    return f"安全拒绝: 禁止调用 '{func.id}'"
            # 拒绝 dunder 属性访问（getattr 绕过、__globals__ 逃逸等）
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    return f"安全拒绝: 禁止访问特殊属性 '{node.attr}'"
            # 拒绝 dunder 名称引用
            elif isinstance(node, ast.Name):
                if node.id.startswith("__") and node.id.endswith("__"):
                    return f"安全拒绝: 禁止引用特殊名称 '{node.id}'"
        return None

    async def execute(self, code: str = "", timeout: int = 10, **kwargs: Any) -> str:
        # AST 静态安全检查
        rejection = self._check_ast(code)
        if rejection:
            return rejection

        # 使用subprocess在隔离环境中执行
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_in_subprocess, code, timeout
            )
            return result
        except Exception as e:
            return f"代码执行错误: {e}"

    def _run_in_subprocess(self, code: str, timeout: int) -> str:
        """在子进程中执行代码"""
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=None,
                env={"PATH": ""},
            )
            output = ""
            if proc.stdout:
                output += proc.stdout
            if proc.stderr:
                output += f"\nSTDERR:\n{proc.stderr}"
            if proc.returncode != 0:
                output += f"\n退出码: {proc.returncode}"
            return output or "代码执行成功（无输出）"
        except subprocess.TimeoutExpired:
            return f"代码执行超时（{timeout}秒）"
        except Exception as e:
            return f"子进程错误: {e}"


class APICallTool(Tool):
    """API调用工具"""
    name = "api_call"
    description = "发送HTTP请求调用API。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "API URL"},
            "method": {"type": "string", "description": "HTTP方法", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            "headers": {"type": "object", "description": "请求头"},
            "body": {"type": "object", "description": "请求体"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
        },
        "required": ["url"],
    }

    async def execute(
        self,
        url: str = "",
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    timeout=float(timeout),
                )
                return f"状态码: {response.status_code}\n响应: {response.text[:2000]}"
        except Exception as e:
            return f"API调用错误: {e}"


class EmbeddingBackend:
    """嵌入向量后端 - 优先 OpenAI 兼容 embeddings，其次 sentence-transformers。

    用于 DocumentRetrievalTool 的真实语义检索。任一后端可用即启用向量检索，
    否则调用方自动降级到 TF-IDF 关键词匹配。
    """

    def __init__(self) -> None:
        self._mode: str | None = None  # "openai" | "st" | None
        self._client: Any = None
        self._model: Any = None
        self._model_name: str = ""
        self._init_backend()

    def _init_backend(self) -> None:
        # 便于直接读到 .env 中的 key（pydantic-settings 不会写入 os.environ）
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        # 1) OpenAI 兼容 embeddings（复用 LLM 的 key / base_url）
        api_key = os.getenv("LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        if api_key:
            try:
                from openai import OpenAI
                kwargs: dict[str, Any] = {"api_key": api_key}
                base_url = os.getenv("LLM_OPENAI_BASE_URL", "") or os.getenv("OPENAI_BASE_URL", "")
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = OpenAI(**kwargs)
                self._model_name = os.getenv("VECTOR_EMBEDDING_MODEL", "") or "text-embedding-3-small"
                self._mode = "openai"
                return
            except Exception:
                self._client = None
        # 2) 本地 sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._mode = "st"
            return
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        return self._mode is not None

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """批量嵌入。失败返回 None，调用方据此降级。

        若后端连续失败（如端点不支持 embeddings），自动停用以避免重复无效请求。
        """
        if not texts or not self.available:
            return None
        try:
            if self._mode == "openai":
                resp = self._client.embeddings.create(model=self._model_name, input=texts)
                return [d.embedding for d in resp.data]
            if self._mode == "st":
                return [list(map(float, v)) for v in self._model.encode(texts)]
        except Exception:
            # 端点不支持/不可用 → 停用后端，后续直接走 TF-IDF 降级
            self._mode = None
            return None
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度（纯 Python，避免强依赖 numpy）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DocumentRetrievalTool(Tool):
    """文档检索工具 - 向量语义检索（带 TF-IDF 降级）

    优先使用真实嵌入向量（OpenAI 兼容 / sentence-transformers）做语义检索；
    当无嵌入后端或嵌入失败时，自动降级到 TF-IDF 关键词匹配，保证始终可用。
    """
    name = "document_retrieval"
    description = "从已加载的文档中检索相关内容。用于回答用户关于文档的问题。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词或问题"},
            "top_k": {"type": "integer", "description": "返回最相关的片段数量", "default": 3},
        },
        "required": ["query"],
    }

    # 进程级共享嵌入后端，避免每个工具实例重复初始化模型
    _shared_embedder: EmbeddingBackend | None = None

    def __init__(self, embedder: EmbeddingBackend | None = None) -> None:
        self._documents: list[dict[str, Any]] = []  # {content, source, chunk_id, embedding?}
        if embedder is not None:
            self._embedder = embedder
        else:
            if DocumentRetrievalTool._shared_embedder is None:
                DocumentRetrievalTool._shared_embedder = EmbeddingBackend()
            self._embedder = DocumentRetrievalTool._shared_embedder
        self._pending_embed = False  # 是否有 chunk 尚未生成 embedding

    def load_file(self, file_path: str) -> int:
        """加载文件并分块"""
        try:
            path = Path(file_path)
            if not path.exists():
                return 0
            content = path.read_text(encoding="utf-8")
            return self.load_text(content, source=str(path.name))
        except Exception:
            return 0

    def load_text(self, text: str, source: str = "user_input") -> int:
        """加载文本并分块（embedding 在首次检索时惰性批量生成）"""
        chunks = self._split_text(text, max_len=500, overlap=50)
        for i, chunk in enumerate(chunks):
            self._documents.append({
                "content": chunk,
                "source": source,
                "chunk_id": f"{source}:{i}",
                "embedding": None,
            })
        if chunks:
            self._pending_embed = True
        return len(chunks)

    def _split_text(self, text: str, max_len: int = 500, overlap: int = 50) -> list[str]:
        """按段落和长度分块"""
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) > max_len and current:
                chunks.append(current.strip())
                # overlap: 保留最后一段作为上下文
                current = current[-overlap:] + "\n\n" + para if overlap else para
            else:
                current = current + "\n\n" + para if current else para
        if current.strip():
            chunks.append(current.strip())
        return chunks if chunks else [text[:max_len]]

    def _ensure_embeddings(self) -> bool:
        """为尚未嵌入的 chunk 批量生成 embedding。返回是否成功启用向量检索。"""
        if not self._embedder.available:
            return False
        if not self._pending_embed:
            return any(d.get("embedding") for d in self._documents)
        missing = [d for d in self._documents if d.get("embedding") is None]
        if missing:
            vectors = self._embedder.embed([d["content"] for d in missing])
            if vectors is None or len(vectors) != len(missing):
                return False
            for d, vec in zip(missing, vectors):
                d["embedding"] = vec
        self._pending_embed = False
        return True

    def _score(self, query: str, text: str) -> float:
        """TF-IDF + 余弦相似度评分（向量后端不可用时的降级路径）"""
        try:
            import numpy as np
            # 构建词汇表
            query_words = query.lower().split()
            text_words = text.lower().split()
            all_words = list(set(query_words + text_words))
            word2idx = {w: i for i, w in enumerate(all_words)}

            # TF-IDF 向量
            def tfidf(words):
                vec = np.zeros(len(all_words))
                for w in words:
                    if w in word2idx:
                        vec[word2idx[w]] += 1
                # TF 归一化
                if len(words) > 0:
                    vec = vec / len(words)
                return vec

            q_vec = tfidf(query_words)
            t_vec = tfidf(text_words)

            # 余弦相似度
            norm_q = np.linalg.norm(q_vec)
            norm_t = np.linalg.norm(t_vec)
            if norm_q == 0 or norm_t == 0:
                return 0.0
            return float(np.dot(q_vec, t_vec) / (norm_q * norm_t))
        except ImportError:
            # fallback: 关键词匹配
            query_words = set(query.lower().split())
            text_lower = text.lower()
            hits = sum(1 for w in query_words if w in text_lower)
            return hits / max(len(query_words), 1)

    async def execute(self, query: str = "", top_k: int = 3, **kwargs: Any) -> str:
        if not self._documents:
            return "没有已加载的文档。请先使用 file_reader 读取文件，或直接将文档内容粘贴给 Agent。"

        # 优先向量语义检索
        method = "TF-IDF"
        scored: list[tuple[float, dict[str, Any]]] = []
        if await asyncio.get_event_loop().run_in_executor(None, self._ensure_embeddings):
            q_emb_list = await asyncio.get_event_loop().run_in_executor(
                None, self._embedder.embed, [query]
            )
            if q_emb_list:
                q_emb = q_emb_list[0]
                scored = [
                    (_cosine(q_emb, doc["embedding"]), doc)
                    for doc in self._documents
                    if doc.get("embedding")
                ]
                method = "向量"

        # 降级：TF-IDF
        if not scored:
            scored = [(self._score(query, doc["content"]), doc) for doc in self._documents]

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, doc in scored[:top_k]:
            if score > 0:
                results.append(
                    f"[来源: {doc['chunk_id']} | 相关度: {score:.0%} | {method}]\n{doc['content']}"
                )

        if not results:
            return "未找到与查询相关的文档片段。"
        return "\n\n---\n\n".join(results)

    def clear(self) -> None:
        self._documents.clear()
        self._pending_embed = False


def create_default_registry() -> ToolRegistry:
    """创建默认工具注册表"""
    registry = ToolRegistry()
    registry.register_many([
        CalculatorTool(),
        WebSearchTool(),
        FileReaderTool(),
        FileWriterTool(),
        CodeExecutorTool(),
        APICallTool(),
        DocumentRetrievalTool(),
    ])
    return registry
