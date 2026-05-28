"""插件管理页面"""

from __future__ import annotations

import streamlit as st

from agentflow.core.plugins import plugin_manager, auto_load_plugins


def render_plugin_page():
    st.markdown("### 🔌 插件管理")

    tab1, tab2 = st.tabs(["已安装插件", "插件目录"])

    with tab1:
        plugins = plugin_manager.list_plugins()

        if not plugins:
            if st.button("加载内置插件"):
                count = auto_load_plugins()
                st.success(f"✅ 已加载 {count} 个插件")
                st.rerun()

        for meta in plugins:
            with st.expander(f"{'✅' if meta.enabled else '⏸️'} {meta.name} v{meta.version}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**类型:** {meta.plugin_type}")
                    st.markdown(f"**描述:** {meta.description}")
                    st.markdown(f"**作者:** {meta.author}")
                    if meta.dependencies:
                        st.markdown(f"**依赖:** {', '.join(meta.dependencies)}")
                with col2:
                    if meta.enabled:
                        if st.button("禁用", key=f"disable_{meta.name}"):
                            plugin_manager.disable(meta.name)
                            st.rerun()
                    else:
                        if st.button("启用", key=f"enable_{meta.name}"):
                            plugin_manager.enable(meta.name)
                            st.rerun()

    with tab2:
        st.markdown("#### 插件目录")
        st.markdown("""
        插件可以放置在以下目录：

        ```
        ~/.agentflow/plugins/     # 用户级插件
        ./plugins/                # 项目级插件
        ```

        插件结构示例：
        ```python
        from agentflow.core.plugins import Plugin, PluginMeta

        class MyPlugin(Plugin):
            def meta(self) -> PluginMeta:
                return PluginMeta(
                    name="my_plugin",
                    version="1.0.0",
                    description="我的自定义插件",
                    plugin_type="tool",
                )

            def register(self, registry):
                # 注册工具/Agent等
                registry.register(MyTool())
        ```
        """)
