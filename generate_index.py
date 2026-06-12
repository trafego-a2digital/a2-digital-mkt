"""
Gera a página index com links para todos os dashboards.
Só para uso interno da A2 Digital — não compartilhar com clientes.
"""

import json, os, base64
from pathlib import Path

ACCOUNTS = json.loads(os.environ["DASHBOARD_ACCOUNTS"])
OUT_DIR  = Path("docs")
OUT_DIR.mkdir(exist_ok=True)

LOGO_B64 = ""
logo_path = Path("assets/logo_a2.png")
if logo_path.exists():
    with open(logo_path, "rb") as f:
        LOGO_B64 = base64.b64encode(f.read()).decode()

rows = ""
for a in ACCOUNTS:
    slug      = a["slug"]
    name      = a["name"]
    platforms = a.get("platforms", [])
    icons     = ""
    if "meta"   in platforms: icons += "<span class='tag meta'>Meta</span>"
    if "google" in platforms: icons += "<span class='tag google'>Google</span>"

    rows += f"""
    <a href="{slug}.html" class="client-row" target="_blank">
      <span class="client-name">{name}</span>
      <span class="client-tags">{icons}</span>
      <span class="client-arrow">→</span>
    </a>"""

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A2 Digital — Dashboards</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:#0a0a0a;color:#efefef;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:60px 20px}}
.logo{{font-size:28px;font-weight:800;color:#F5A623;margin-bottom:8px;letter-spacing:-.02em}}
.subtitle{{font-size:13px;color:#555;margin-bottom:48px}}
.list{{width:100%;max-width:600px;display:flex;flex-direction:column;gap:8px}}
.client-row{{display:flex;align-items:center;gap:12px;padding:16px 20px;background:#111;border:1px solid #222;border-radius:10px;text-decoration:none;color:#efefef;transition:all .15s}}
.client-row:hover{{border-color:rgba(245,166,35,.4);background:#161616;transform:translateX(4px)}}
.client-name{{flex:1;font-size:14px;font-weight:600}}
.client-tags{{display:flex;gap:6px}}
.tag{{font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px}}
.meta{{background:rgba(59,130,246,.15);color:#3b82f6}}
.google{{background:rgba(34,197,94,.15);color:#22c55e}}
.client-arrow{{color:#444;font-size:16px}}
.footer{{margin-top:48px;font-size:11px;color:#333}}
</style>
</head>
<body>
  {f'<img src="data:image/png;base64,{LOGO_B64}" style="height:72px;margin-bottom:8px" alt="A2 Digital">' if LOGO_B64 else '<div class="logo">A2 Digital</div>'}
  <div class="subtitle">Painel interno — dashboards dos clientes</div>
  <div class="list">{rows}</div>
  <div class="footer">Atualizado diariamente às 08:00 · A2 Digital Marketing</div>
</body>
</html>"""

with open(OUT_DIR / "index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Index gerado com {len(ACCOUNTS)} clientes.")
