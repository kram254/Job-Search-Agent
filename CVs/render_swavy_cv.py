#!/usr/bin/env python3
"""Render the Swavy-targeted full-stack CV (markdown) to a single-column,
text-extractable PDF via xhtml2pdf — same styling approach as the micro1 CV."""
import re
from pathlib import Path
from xhtml2pdf import pisa

SRC = Path(__file__).parent / "Swavy_FullStack_Ndaliro.md"
OUT = Path(__file__).parent / "Swavy_FullStack_Ndaliro.pdf"

md = SRC.read_text(encoding="utf-8")

lines = md.splitlines()
html_parts = []
in_list = False
for line in lines:
    stripped = line.strip()
    if not stripped:
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        continue
    if stripped == "---":
        if in_list: html_parts.append("</ul>"); in_list = False
        continue
    if stripped.startswith("### "):
        if in_list: html_parts.append("</ul>"); in_list = False
        html_parts.append(f"<h3>{stripped[4:]}</h3>")
    elif stripped.startswith("## "):
        if in_list: html_parts.append("</ul>"); in_list = False
        html_parts.append(f"<h2>{stripped[3:]}</h2>")
    elif stripped.startswith("# "):
        if in_list: html_parts.append("</ul>"); in_list = False
        html_parts.append(f"<h1>{stripped[2:]}</h1>")
    elif stripped.startswith("- "):
        if not in_list:
            html_parts.append("<ul>")
            in_list = True
        html_parts.append(f"<li>{stripped[2:]}</li>")
    elif stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
        html_parts.append(f"<p class='meta'>{stripped.strip('*')}</p>")
    else:
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        html_parts.append(f"<p>{stripped}</p>")
if in_list:
    html_parts.append("</ul>")

content = "\n".join(html_parts)
content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
content = re.sub(r"\*(.+?)\*", r"<i>\1</i>", content)
content = content.replace("**", "").replace("*", "")

html = f"""<!DOCTYPE html>
<html><head><style>
@page {{ size: A4; margin: 1.4cm 1.6cm; }}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 9.6pt; color: #1a1a1a; line-height: 1.38; }}
h1 {{ font-size: 17pt; margin: 0 0 2pt 0; }}
h2 {{ font-size: 11pt; margin: 10pt 0 4pt 0; border-bottom: 1px solid #444; padding-bottom: 2pt; }}
h3 {{ font-size: 10pt; margin: 7pt 0 2pt 0; }}
p {{ margin: 2pt 0; }}
p.meta {{ font-size: 8.6pt; color: #444; font-style: italic; margin: 0 0 4pt 0; }}
ul {{ margin: 2pt 0 5pt 0; padding-left: 14pt; }}
li {{ margin-bottom: 2.2pt; }}
</style></head><body>{content}</body></html>"""

with open(OUT, "wb") as f:
    status = pisa.CreatePDF(html, dest=f)

print("PDF written:", OUT, "| errors:", status.err)
