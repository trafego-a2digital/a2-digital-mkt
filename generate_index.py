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

# Favicon (ícone da aba do navegador): símbolo "A" da A2, 64x64 PNG embutido
FAVICON_B64 = "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"

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
<link rel="icon" type="image/png" href="data:image/png;base64,{FAVICON_B64}">
<link rel="apple-touch-icon" href="data:image/png;base64,{FAVICON_B64}">
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
