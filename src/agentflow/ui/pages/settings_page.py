"""设置页面 - API Key 配置"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st


ENV_FILE = Path(__file__).resolve().parents[4] / ".env"

MIMO_BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"
MIMO_MODELS = [
    "mimo-v2.5-pro",
    "mimo-v2.5",
    "mimo-v2-pro",
    "mimo-v2-omni",
]


def _load_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _save_env_file(updates: dict[str, str]) -> None:
    existing = _load_env_file()
    existing.update(updates)

    lines: list[str] = []
    seen: set[str] = set()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            if "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    lines.append(f"{k}={updates[k]}")
                    seen.add(k)
                    continue
            lines.append(line)

    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_settings_page() -> None:
    st.markdown("### API 设置")
    st.caption("配置 LLM API Key，创建 Agent 时自动使用。配置会保存到项目根目录 `.env` 文件。")

    env = _load_env_file()

    providers = ["mimo", "openai", "anthropic", "local"]
    current_provider = env.get("LLM_PROVIDER", st.session_state.get("settings_provider", "mimo"))
    provider = st.selectbox(
        "LLM 提供商",
        providers,
        index=providers.index(current_provider) if current_provider in providers else 0,
        format_func=lambda x: {
            "mimo": "MiMo (小米 — 默认)",
            "openai": "OpenAI (GPT 系列)",
            "anthropic": "Anthropic (Claude 官方)",
            "local": "本地模型 (Ollama)",
        }[x],
    )

    api_key = ""
    model = ""
    base_url = ""

    if provider == "mimo":
        api_key = st.text_input(
            "MiMo API Key",
            value=env.get("LLM_API_KEY", st.session_state.get("settings_mimo_key", "")),
            type="password",
            placeholder="tp-...",
        )
        model = st.selectbox("模型", MIMO_MODELS, index=0)
        base_url = MIMO_BASE_URL
        st.caption(f"Endpoint: `{MIMO_BASE_URL}`")

    elif provider == "openai":
        api_key = st.text_input(
            "OpenAI API Key",
            value=env.get("LLM_API_KEY", st.session_state.get("settings_openai_key", "")),
            type="password",
            placeholder="sk-...",
        )
        model = st.selectbox(
            "模型",
            ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            index=1,
        )

    elif provider == "anthropic":
        api_key = st.text_input(
            "Anthropic API Key",
            value=env.get("ANTHROPIC_API_KEY", st.session_state.get("settings_anthropic_key", "")),
            type="password",
            placeholder="sk-ant-...",
        )
        model = st.selectbox(
            "模型",
            ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
            index=0,
        )

    elif provider == "local":
        base_url = st.text_input(
            "本地模型地址",
            value=env.get("LOCAL_LLM_BASE_URL", "http://localhost:11434"),
        )
        model = st.text_input("模型名称", value=env.get("LOCAL_LLM_MODEL", "llama3"))
        st.info("需要本地运行 Ollama 等兼容 OpenAI API 的服务")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        temperature = st.slider("Temperature", 0.0, 2.0, float(env.get("LLM_TEMPERATURE", "0.7")), 0.1)
    with col2:
        max_tokens = st.number_input("Max Tokens", 256, 128000, int(env.get("LLM_MAX_TOKENS", "4096")), 256)

    st.markdown("---")

    if st.button("保存配置", type="primary", use_container_width=True):
        updates: dict[str, str] = {
            "LLM_PROVIDER": provider,
            "LLM_MODEL": model,
            "LLM_TEMPERATURE": str(temperature),
            "LLM_MAX_TOKENS": str(max_tokens),
        }
        if provider == "mimo":
            updates["LLM_API_KEY"] = api_key
            updates["LLM_OPENAI_BASE_URL"] = base_url
        elif provider == "openai":
            updates["LLM_API_KEY"] = api_key
            updates["LLM_OPENAI_BASE_URL"] = ""
        elif provider == "anthropic":
            updates["ANTHROPIC_API_KEY"] = api_key
            updates["LLM_OPENAI_BASE_URL"] = ""
        elif provider == "local":
            updates["LOCAL_LLM_BASE_URL"] = base_url
            updates["LOCAL_LLM_MODEL"] = model

        try:
            _save_env_file(updates)
            st.success("配置已保存到 .env 文件")
        except Exception as e:
            st.error(f"保存失败: {e}")

        # 同步到 session state
        st.session_state["settings_provider"] = provider
        st.session_state["settings_model"] = model
        st.session_state["settings_temperature"] = temperature
        st.session_state["settings_max_tokens"] = max_tokens
        if provider == "mimo":
            st.session_state["settings_mimo_key"] = api_key
        elif provider == "openai":
            st.session_state["settings_openai_key"] = api_key
        elif provider == "anthropic":
            st.session_state["settings_anthropic_key"] = api_key

    # 当前状态
    st.markdown("#### 当前配置")
    if provider == "mimo":
        key = st.session_state.get("settings_mimo_key", env.get("LLM_API_KEY", ""))
        if key:
            st.success(f"MiMo 已连接 (***{key[-4:]})  模型: {model}")
        else:
            st.warning("未配置 MiMo API Key")
    elif provider == "openai":
        key = st.session_state.get("settings_openai_key", env.get("LLM_API_KEY", ""))
        if key:
            st.success(f"OpenAI 已连接 (***{key[-4:]})")
        else:
            st.warning("未配置 OpenAI API Key")
    elif provider == "anthropic":
        key = st.session_state.get("settings_anthropic_key", env.get("ANTHROPIC_API_KEY", ""))
        if key:
            st.success(f"Anthropic 已连接 (***{key[-4:]})")
        else:
            st.warning("未配置 Anthropic API Key")
    elif provider == "local":
            st.info(f"本地模型: {base_url}")
