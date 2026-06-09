"""扫描前端乱码和不和谐问题"""
import re, sys, os
from pathlib import Path

# Windows 编码修复
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

print("=" * 60)
print("  前端问题扫描")
print("=" * 60)

content = Path("src/agentflow/ui/app.py").read_text(encoding="utf-8")

# 1. 找所有 st.info/st.warning/st.success/st.error 中的 emoji
print("\n[1] 提示信息中的 emoji:")
info_pattern = re.findall(r'st\.(info|warning|success|error)\((["\'])(.*?)\2', content)
for typ, _, text in info_pattern:
    has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', text))
    marker = "HAS_EMOJI" if has_emoji else "clean"
    print(f"  st.{typ}: {text[:50]}  [{marker}]")

# 2. 找所有按钮文字
print("\n[2] 按钮文字:")
buttons = re.findall(r'st\.button\("([^"]+)"', content)
for b in set(buttons):
    has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', b))
    marker = "HAS_EMOJI" if has_emoji else "clean"
    print(f'  "{b}"  [{marker}]')

# 3. Tab 名称
print("\n[3] Tab 名称:")
tab_match = re.search(r'st\.tabs\(\[(.*?)\]\)', content, re.DOTALL)
if tab_match:
    tabs = re.findall(r'"([^"]+)"', tab_match.group(1))
    for t in tabs:
        has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', t))
        marker = "HAS_EMOJI" if has_emoji else "clean"
        print(f'  "{t}"  [{marker}]')

# 4. HTML 模板中的文字
print("\n[4] HTML 模板文字:")
html_texts = re.findall(r'<div class="[^"]*"[^>]*>([^<]+)</div>', content)
for t in html_texts[:15]:
    t = t.strip()
    if t and not t.startswith("{"):
        has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', t))
        marker = "HAS_EMOJI" if has_emoji else "clean"
        print(f'  "{t[:40]}"  [{marker}]')

# 5. CSS 中的中文字体
print("\n[5] CSS 字体:")
font_match = re.findall(r'font-family:\s*([^;]+)', content)
for f in set(font_match):
    print(f"  {f.strip()}")

# 6. 侧边栏 expander 标题
print("\n[6] 侧边栏区域标题:")
expanders = re.findall(r'st\.expander\("([^"]+)"', content)
for e in expanders:
    has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', e))
    marker = "HAS_EMOJI" if has_emoji else "clean"
    print(f'  "{e}"  [{marker}]')

# 7. st.markdown 标题
print("\n[7] Markdown 标题:")
headers = re.findall(r'st\.markdown\("([^"]{1,30})"', content)
for h in headers[:15]:
    has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', h))
    marker = "HAS_EMOJI" if has_emoji else "clean"
    print(f'  "{h}"  [{marker}]')

print("\n" + "=" * 60)
print("  扫描完成")
print("=" * 60)
