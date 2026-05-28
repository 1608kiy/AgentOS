"""可视化工作流设计器 - Streamlit自定义组件"""

from __future__ import annotations

import json
import streamlit as st
import streamlit.components.v1 as components


def render_workflow_designer(nodes: list[dict] | None = None, height: int = 600):
    """渲染可视化工作流设计器"""

    default_nodes = nodes or [
        {"id": "start", "label": "开始", "type": "start", "x": 50, "y": 200},
        {"id": "end", "label": "结束", "type": "end", "x": 700, "y": 200},
    ]

    nodes_json = json.dumps(default_nodes)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Inter', sans-serif; background: #f8fafc; overflow: hidden; }}

            .toolbar {{
                background: white;
                border-bottom: 1px solid #e5e7eb;
                padding: 8px 16px;
                display: flex;
                gap: 8px;
                align-items: center;
            }}
            .toolbar button {{
                padding: 6px 14px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: white;
                cursor: pointer;
                font-size: 13px;
                transition: all 0.15s;
            }}
            .toolbar button:hover {{
                background: #f3f4f6;
                border-color: #667eea;
            }}
            .toolbar .sep {{ width: 1px; height: 24px; background: #e5e7eb; }}

            canvas {{ display: block; cursor: crosshair; }}

            .node-popup {{
                display: none;
                position: absolute;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.12);
                z-index: 100;
                min-width: 200px;
            }}
            .node-popup.show {{ display: block; }}
            .node-popup label {{
                display: block;
                font-size: 12px;
                color: #6b7280;
                margin-bottom: 4px;
            }}
            .node-popup input, .node-popup select {{
                width: 100%;
                padding: 6px 10px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-bottom: 10px;
                font-size: 13px;
            }}
            .node-popup button {{
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                margin-right: 6px;
            }}
            .btn-save {{ background: #667eea; color: white; }}
            .btn-cancel {{ background: #f3f4f6; color: #374151; }}
            .btn-delete {{ background: #fee2e2; color: #991b1b; }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <button onclick="addNode('agent')">🤖 Agent节点</button>
            <button onclick="addNode('tool')">🔧 工具节点</button>
            <button onclick="addNode('condition')">🔀 条件节点</button>
            <button onclick="addNode('human')">👤 人工审核</button>
            <div class="sep"></div>
            <button onclick="clearAll()">🗑️ 清空</button>
            <button onclick="exportWorkflow()">📤 导出JSON</button>
        </div>

        <canvas id="canvas"></canvas>

        <div id="nodePopup" class="node-popup">
            <label>节点名称</label>
            <input type="text" id="nodeName" placeholder="输入名称">
            <label>节点类型</label>
            <select id="nodeType">
                <option value="agent">Agent</option>
                <option value="tool">工具</option>
                <option value="condition">条件</option>
                <option value="human">人工审核</option>
            </select>
            <label>任务描述</label>
            <input type="text" id="nodeTask" placeholder="描述任务...">
            <div style="margin-top: 12px;">
                <button class="btn-save" onclick="saveNode()">保存</button>
                <button class="btn-cancel" onclick="closePopup()">取消</button>
                <button class="btn-delete" onclick="deleteNode()">删除</button>
            </div>
        </div>

        <script>
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            const popup = document.getElementById('nodePopup');

            let nodes = {nodes_json};
            let edges = [];
            let selectedNode = null;
            let dragging = null;
            let connecting = null;
            let editingNode = null;

            const colors = {{
                start: '#10b981',
                end: '#ef4444',
                agent: '#667eea',
                tool: '#f59e0b',
                condition: '#8b5cf6',
                human: '#ec4899',
            }};

            function resize() {{
                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = {height} - 50;
                draw();
            }}

            function draw() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // 绘制网格
                ctx.strokeStyle = '#f1f5f9';
                ctx.lineWidth = 1;
                for (let x = 0; x < canvas.width; x += 40) {{
                    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
                }}
                for (let y = 0; y < canvas.height; y += 40) {{
                    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
                }}

                // 绘制边
                edges.forEach(e => {{
                    const from = nodes.find(n => n.id === e.from);
                    const to = nodes.find(n => n.id === e.to);
                    if (from && to) drawEdge(from, to);
                }});

                // 绘制节点
                nodes.forEach(n => drawNode(n));
            }}

            function drawNode(n) {{
                const w = 140, h = 50, r = 10;
                const color = colors[n.type] || '#667eea';

                // 阴影
                ctx.shadowColor = 'rgba(0,0,0,0.1)';
                ctx.shadowBlur = 10;
                ctx.shadowOffsetY = 4;

                // 背景
                ctx.fillStyle = 'white';
                ctx.strokeStyle = selectedNode === n ? color : '#e5e7eb';
                ctx.lineWidth = selectedNode === n ? 3 : 1.5;
                ctx.beginPath();
                ctx.roundRect(n.x, n.y, w, h, r);
                ctx.fill();
                ctx.stroke();

                ctx.shadowColor = 'transparent';

                // 颜色条
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.roundRect(n.x, n.y, 6, h, [r, 0, 0, r]);
                ctx.fill();

                // 文字
                ctx.fillStyle = '#1f2937';
                ctx.font = '13px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(n.label || n.id, n.x + w/2, n.y + h/2 + 4);

                // 类型标签
                ctx.fillStyle = color;
                ctx.font = '10px Inter, sans-serif';
                ctx.fillText(n.type.toUpperCase(), n.x + w/2, n.y + 14);
            }}

            function drawEdge(from, to) {{
                const fw = 140, fh = 50;
                const fx = from.x + fw, fy = from.y + fh/2;
                const tx = to.x, ty = to.y + fh/2;
                const cx = (fx + tx) / 2;

                ctx.strokeStyle = '#94a3b8';
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 3]);
                ctx.beginPath();
                ctx.moveTo(fx, fy);
                ctx.bezierCurveTo(cx, fy, cx, ty, tx, ty);
                ctx.stroke();
                ctx.setLineDash([]);

                // 箭头
                const angle = Math.atan2(ty - fy, tx - fx);
                ctx.fillStyle = '#94a3b8';
                ctx.beginPath();
                ctx.moveTo(tx, ty);
                ctx.lineTo(tx - 10*Math.cos(angle-0.3), ty - 10*Math.sin(angle-0.3));
                ctx.lineTo(tx - 10*Math.cos(angle+0.3), ty - 10*Math.sin(angle+0.3));
                ctx.fill();
            }}

            function getNodeAt(x, y) {{
                return nodes.find(n => x >= n.x && x <= n.x+140 && y >= n.y && y <= n.y+50);
            }}

            canvas.addEventListener('mousedown', e => {{
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const node = getNodeAt(x, y);

                if (node) {{
                    if (e.shiftKey) {{
                        connecting = node;
                    }} else {{
                        dragging = {{ node, offsetX: x - node.x, offsetY: y - node.y }};
                        selectedNode = node;
                    }}
                }} else {{
                    selectedNode = null;
                }}
                draw();
            }});

            canvas.addEventListener('mousemove', e => {{
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                if (dragging) {{
                    dragging.node.x = x - dragging.offsetX;
                    dragging.node.y = y - dragging.offsetY;
                    draw();
                }}
            }});

            canvas.addEventListener('mouseup', e => {{
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                if (connecting) {{
                    const target = getNodeAt(x, y);
                    if (target && target !== connecting) {{
                        edges.push({{ from: connecting.id, to: target.id }});
                    }}
                    connecting = null;
                    draw();
                }}
                dragging = null;
            }});

            canvas.addEventListener('dblclick', e => {{
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const node = getNodeAt(x, y);

                if (node) {{
                    editingNode = node;
                    document.getElementById('nodeName').value = node.label;
                    document.getElementById('nodeType').value = node.type;
                    document.getElementById('nodeTask').value = node.task || '';
                    popup.style.left = (e.clientX - 100) + 'px';
                    popup.style.top = (e.clientY + 10) + 'px';
                    popup.classList.add('show');
                }}
            }});

            function addNode(type) {{
                const id = 'node_' + Date.now();
                const labels = {{ agent: 'Agent', tool: '工具', condition: '条件', human: '人工审核' }};
                nodes.push({{
                    id, label: labels[type] || type, type,
                    x: 100 + Math.random()*400, y: 100 + Math.random()*200,
                }});
                draw();
            }}

            function saveNode() {{
                if (editingNode) {{
                    editingNode.label = document.getElementById('nodeName').value;
                    editingNode.type = document.getElementById('nodeType').value;
                    editingNode.task = document.getElementById('nodeTask').value;
                }}
                closePopup();
                draw();
            }}

            function deleteNode() {{
                if (editingNode) {{
                    nodes = nodes.filter(n => n.id !== editingNode.id);
                    edges = edges.filter(e => e.from !== editingNode.id && e.to !== editingNode.id);
                }}
                closePopup();
                draw();
            }}

            function closePopup() {{
                popup.classList.remove('show');
                editingNode = null;
            }}

            function clearAll() {{
                nodes = [
                    {{ id: 'start', label: '开始', type: 'start', x: 50, y: 200 }},
                    {{ id: 'end', label: '结束', type: 'end', x: 700, y: 200 }},
                ];
                edges = [];
                draw();
            }}

            function exportWorkflow() {{
                const data = {{ nodes, edges }};
                const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'workflow.json'; a.click();
            }}

            window.addEventListener('resize', resize);
            resize();
        </script>
    </body>
    </html>
    """

    components.html(html, height=height)


# Streamlit页面入口
if __name__ == "__main__":
    st.set_page_config(page_title="工作流设计器", layout="wide")
    st.markdown("### 🎨 可视化工作流设计器")
    st.caption("双击节点编辑 | Shift+拖拽连线 | 拖拽移动节点")
    render_workflow_designer()
