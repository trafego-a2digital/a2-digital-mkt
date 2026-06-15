"""
gerar_html_a2.py — Gera o HTML do Relatório A2 (layout oficial da agência)
a partir do payload de dados semanais, com logo embutida em base64.

Logo: o script procura o arquivo definido em config (logo_path) dentro do
repositório — padrão: assets/logo.png — e embute como data URI.
"""

import base64
import os
from datetime import datetime
from comum import fmt_brl, TZ_BR

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
:root{--amarelo:#FFB800;--fundo:#0a0a0a;--superficie:#0d0d0d;--card:#111;
--borda:#1e1e1e;--texto:#e8e8e8;--texto-sutil:#aaa;--texto-des:#444;
--verde:#4ade80;--vermelho:#f87171;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--fundo);color:var(--texto);font-family:'Inter',Arial,sans-serif;}
.cover,.page{min-height:100vh;padding:48px 56px;background:var(--fundo);position:relative;}
.cover-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:90px;}
.logo{height:44px;}
.logo-sm{height:28px;}
.badge-rel{background:rgba(255,184,0,.12);border:1px solid rgba(255,184,0,.3);
color:var(--amarelo);padding:6px 14px;border-radius:20px;font-size:12px;font-weight:600;}
.periodo-label{color:var(--amarelo);font-size:13px;font-weight:600;letter-spacing:2px;
text-transform:uppercase;margin-bottom:14px;}
.cliente{font-size:48px;font-weight:800;line-height:1.1;margin-bottom:10px;}
.subtitulo{color:var(--texto-sutil);font-size:16px;margin-bottom:36px;}
.divisor{height:3px;background:linear-gradient(90deg,var(--amarelo),transparent);
border:none;margin-bottom:40px;}
.meta-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;}
.meta-item{background:var(--card);border:1px solid var(--borda);border-radius:10px;padding:18px;}
.meta-item .ml{color:var(--texto-sutil);font-size:11px;text-transform:uppercase;
letter-spacing:1px;margin-bottom:6px;}
.meta-item .mv{font-size:18px;font-weight:700;}
.footer{position:absolute;bottom:32px;left:56px;right:56px;display:flex;
justify-content:space-between;color:var(--texto-des);font-size:11px;}
.page-hdr{display:flex;justify-content:space-between;align-items:center;
margin-bottom:32px;border-bottom:1px solid var(--borda);padding-bottom:16px;}
.page-hdr .sec{color:var(--amarelo);font-size:11px;font-weight:600;
letter-spacing:2px;text-transform:uppercase;}
.page-hdr h2{font-size:22px;font-weight:700;margin-top:4px;}
.camp{background:var(--superficie);border:1px solid var(--borda);border-radius:12px;
padding:24px;margin-bottom:24px;}
.camp-hdr{display:flex;justify-content:space-between;align-items:center;
border-bottom:2px solid var(--amarelo);padding-bottom:14px;margin-bottom:18px;}
.camp-hdr h3{font-size:16px;font-weight:700;}
.badge{background:rgba(255,184,0,.12);border:1px solid rgba(255,184,0,.3);
color:var(--amarelo);padding:4px 12px;border-radius:14px;font-size:11px;font-weight:600;}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px;}
.kpi{background:var(--card);border:1px solid var(--borda);border-radius:8px;
padding:14px;position:relative;overflow:hidden;}
.kpi::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--amarelo);}
.kpi.hl{background:linear-gradient(135deg,#1a1500,#111);}
.kpi.hl .kv{color:var(--amarelo);}
.kpi .kl{color:var(--texto-sutil);font-size:10px;text-transform:uppercase;
letter-spacing:1px;margin-bottom:5px;}
.kpi .kv{font-size:17px;font-weight:700;}
.creats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.creat{background:var(--card);border:1px solid var(--borda);border-radius:8px;padding:14px;}
.creat.vazio{background:#0f0f0f;display:flex;align-items:center;justify-content:center;
color:var(--texto-des);font-size:11px;text-align:center;min-height:120px;}
.creat-top{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.creat-num{width:20px;height:20px;border-radius:50%;background:var(--amarelo);
color:#000;font-size:11px;font-weight:800;display:flex;align-items:center;
justify-content:center;flex-shrink:0;}
.creat-nome{font-size:12px;font-weight:600;line-height:1.3;}
.creat-stats{color:var(--texto-sutil);font-size:11px;line-height:1.7;margin-bottom:10px;}
.creat-stats b{color:var(--texto);}
.plink{display:inline-block;background:rgba(255,184,0,.08);border:1px solid rgba(255,184,0,.25);
color:var(--amarelo);padding:5px 10px;border-radius:6px;font-size:10px;
text-decoration:none;font-weight:600;}
.new-badge{background:rgba(74,222,128,.12);border:1px solid rgba(74,222,128,.35);
color:var(--verde);padding:2px 8px;border-radius:10px;font-size:9px;font-weight:700;margin-left:6px;}
.stbl{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:28px;}
.stbl th{background:var(--amarelo);color:#000;padding:10px 12px;text-align:left;
font-weight:700;font-size:11px;text-transform:uppercase;}
.stbl td{padding:10px 12px;border-bottom:1px solid var(--borda);}
.stbl tr:nth-child(even) td{background:var(--card);}
.cpr-bom{color:var(--verde);font-weight:700;}
.cpr-ruim{color:var(--vermelho);font-weight:700;}
.abox{border-left:3px solid var(--amarelo);background:linear-gradient(135deg,#141001,#0d0d0d);
border-radius:0 10px 10px 0;padding:22px 24px;font-size:13px;line-height:1.9;}
.abox h4{color:var(--amarelo);font-size:13px;text-transform:uppercase;
letter-spacing:1px;margin-bottom:10px;}
@media print{body{background:#0a0a0a!important;-webkit-print-color-adjust:exact;
print-color-adjust:exact;}.page,.cover{page-break-after:always;}}
"""


def carregar_logo_b64(logo_path):
    """Lê a logo do repositório e devolve data URI base64 (ou None)."""
    raiz = os.path.join(os.path.dirname(__file__), "..")
    caminho = os.path.join(raiz, logo_path)
    if not os.path.isfile(caminho):
        # tenta qualquer png/jpg dentro de assets/
        pasta = os.path.join(raiz, "assets")
        if os.path.isdir(pasta):
            for f in sorted(os.listdir(pasta)):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    caminho = os.path.join(pasta, f)
                    break
    if not os.path.isfile(caminho):
        return None
    ext = "png" if caminho.lower().endswith(".png") else "jpeg"
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{ext};base64,{b64}"


def _logo_tag(logo, classe="logo"):
    if logo:
        return f'<img src="{logo}" class="{classe}" alt="A2 Digital">'
    return '<div style="color:#FFB800;font-weight:800;font-size:20px;">A2 DIGITAL</div>'


def _classe_cpr(cpr, cpr_medio):
    if cpr is None or not cpr_medio:
        return ""
    return "cpr-bom" if cpr <= cpr_medio else ("cpr-ruim" if cpr > cpr_medio * 1.5 else "")


def _bloco_criativos(criativos):
    cards = []
    for i, cr in enumerate(criativos[:3], 1):
        novo = '<span class="new-badge">Novo</span>' if cr.get("novo") else ""
        link = (f'<a class="plink" href="{cr["preview"]}">▶ Ver anúncio</a>'
                if cr.get("preview") else "")
        res_lbl = (f'Resultados: <b>{cr["resultados"]}</b> · CPR: <b>{fmt_brl(cr["cpr"])}</b><br>'
                   if cr.get("resultados") else
                   f'Cliques: <b>{cr["cliques"]}</b> · CTR: <b>{cr["ctr"]:.2f}%</b><br>')
        cards.append(f"""<div class="creat">
<div class="creat-top"><div class="creat-num">{i}</div>
<div class="creat-nome">{cr["nome"]}{novo}</div></div>
<div class="creat-stats">{res_lbl}Investido: <b>{fmt_brl(cr["gasto"])}</b></div>
{link}</div>""")
    while len(cards) < 3:
        n = len(criativos)
        cards.append(f'<div class="creat vazio">Apenas {n} criativo(s) ativo(s)<br>nesta campanha</div>')
    return '<div class="creats">' + "".join(cards) + "</div>"


def _bloco_campanha(c):
    obj = c.get("objetivo", "").replace("OUTCOME_", "").title() or "—"
    res = c["resultados"] if c["resultados"] else f'{c["cliques"]} cliques'
    cpr = fmt_brl(c["cpr"]) if c["cpr"] else "—"
    return f"""<div class="camp">
<div class="camp-hdr"><h3>{c["nome"]}</h3><span class="badge">{obj}</span></div>
<div class="kpis">
<div class="kpi"><div class="kl">Objetivo</div><div class="kv">{obj}</div></div>
<div class="kpi"><div class="kl">Resultados</div><div class="kv">{res}</div></div>
<div class="kpi"><div class="kl">Valor Investido</div><div class="kv">{fmt_brl(c["gasto"])}</div></div>
<div class="kpi hl"><div class="kl">Custo/Resultado</div><div class="kv">{cpr}</div></div>
</div>
{_bloco_criativos(c.get("top_criativos", []))}
</div>"""


def _analise(payload):
    t = payload["totais"]
    camps = [c for c in payload["campanhas"] if c["cpr"]]
    linhas = [f"<b>Total investido:</b> {fmt_brl(t['investido'])} · "
              f"<b>Conversões:</b> {t['resultados']} · "
              f"<b>CPR médio:</b> {fmt_brl(t['cpr_medio'])}"]
    if camps:
        melhor = min(camps, key=lambda c: c["cpr"])
        linhas.append(f"✅ <b>Melhor CPR:</b> {melhor['nome']} — {fmt_brl(melhor['cpr'])}")
        if t["cpr_medio"]:
            ruins = [c for c in camps if c["cpr"] > t["cpr_medio"] * 1.5]
            for c in ruins[:3]:
                linhas.append(f"⚠️ <b>Alerta:</b> {c['nome']} com CPR de {fmt_brl(c['cpr'])}, "
                              f"acima da média do período — revisar segmentação/criativos.")
        novos_bons = [cr for c in payload["campanhas"]
                      for cr in c.get("top_criativos", [])
                      if cr.get("novo") and cr.get("cpr") and t["cpr_medio"]
                      and cr["cpr"] <= t["cpr_medio"]]
        for cr in novos_bons[:2]:
            linhas.append(f"✅ <b>Destaque:</b> criativo novo \"{cr['nome']}\" "
                          f"já performando com CPR de {fmt_brl(cr['cpr'])} — candidato a escala.")
        linhas.append("<b>Recomendações:</b> concentrar verba nas campanhas de menor CPR; "
                      "substituir criativos sinalizados em alerta; manter monitoramento diário.")
    return "<br>".join(linhas)


def gerar_html(payload, logo_b64):
    p = payload["periodo"]
    ini = datetime.fromisoformat(p["inicio"]).strftime("%d/%m")
    fim = datetime.fromisoformat(p["fim"]).strftime("%d/%m/%Y")
    t = payload["totais"]
    gerado = datetime.now(TZ_BR).strftime("%d/%m/%Y")
    camps = payload["campanhas"]
    n_ativas = len(camps)

    blocos_camp = "".join(_bloco_campanha(c) for c in camps)

    linhas_tbl = "".join(
        f"<tr><td>{c['nome']}</td><td>{fmt_brl(c['gasto'])}</td>"
        f"<td>{c['resultados'] or '—'}</td>"
        f"<td class=\"{_classe_cpr(c['cpr'], t['cpr_medio'])}\">{fmt_brl(c['cpr'])}</td></tr>"
        for c in camps)

    footer = (f'<div class="footer"><span>A2 Digital Marketing</span>'
              f'<span>Gerado em {gerado} · Uso interno — Confidencial</span></div>')

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Relatório A2 — {payload["cliente"]}</title><style>{CSS}</style></head><body>

<div class="cover">
<div class="cover-top">{_logo_tag(logo_b64)}<span class="badge-rel">Relatório Semanal</span></div>
<div class="periodo-label">Meta Ads · {ini} a {fim}</div>
<h1 class="cliente">{payload["cliente"]}</h1>
<p class="subtitulo">Relatório de Performance — Tráfego Pago</p>
<hr class="divisor">
<div class="meta-grid">
<div class="meta-item"><div class="ml">Período</div><div class="mv">{ini} – {fim}</div></div>
<div class="meta-item"><div class="ml">Conta de Anúncios</div><div class="mv">{payload["account_id"]}</div></div>
<div class="meta-item"><div class="ml">Total Investido</div><div class="mv">{fmt_brl(t["investido"])}</div></div>
<div class="meta-item"><div class="ml">Campanhas Ativas</div><div class="mv">{n_ativas}</div></div>
<div class="meta-item"><div class="ml">Total de Msgs/Leads</div><div class="mv">{t["resultados"]}</div></div>
<div class="meta-item"><div class="ml">CPR Médio</div><div class="mv">{fmt_brl(t["cpr_medio"])}</div></div>
</div>
{footer}
</div>

<div class="page">
<div class="page-hdr"><div><div class="sec">Desempenho</div><h2>Campanhas</h2></div>
{_logo_tag(logo_b64, "logo-sm")}</div>
{blocos_camp}
{footer}
</div>

<div class="page">
<div class="page-hdr"><div><div class="sec">Consolidado</div><h2>Resumo &amp; Análise</h2></div>
{_logo_tag(logo_b64, "logo-sm")}</div>
<table class="stbl"><thead><tr><th>Campanha</th><th>Investido</th>
<th>Resultados</th><th>CPR</th></tr></thead><tbody>{linhas_tbl}</tbody></table>
<div class="abox"><h4>Análise da Semana</h4>{_analise(payload)}</div>
{footer}
</div>

</body></html>"""
