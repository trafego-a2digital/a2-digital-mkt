"""
A2 Digital — Dashboard Generator
Busca dados da API do Meta Ads e gera HTML por conta.

Uso:
  python generate_dashboard.py

Variáveis de ambiente necessárias:
  META_ACCESS_TOKEN   — token do System User
  DASHBOARD_ACCOUNTS  — JSON com configuração das contas
  
Formato de DASHBOARD_ACCOUNTS:
  [
    {
      "id": "act_XXXXXXXXXX",
      "name": "Dra. Camila Firme",
      "niche": "Cirurgia Plástica",
      "slug": "dra-camila-firme",
      "result_label": "Mensagens Iniciadas",
      "result_event": "onsite_conversion.messaging_conversation_started_7d"
    },
    ...
  ]
"""

import os, json, sys, base64, datetime, requests
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
TOKEN    = os.environ["META_ACCESS_TOKEN"]
ACCOUNTS = json.loads(os.environ["DASHBOARD_ACCOUNTS"])
API_VER  = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"
OUT_DIR  = Path("docs")          # GitHub Pages serve a pasta /docs
OUT_DIR.mkdir(exist_ok=True)

# Logo A2 em base64 — será embutida no HTML
LOGO_PATH = Path("logo_a2.png")
LOGO_B64  = ""
if LOGO_PATH.exists():
    with open(LOGO_PATH, "rb") as f:
        LOGO_B64 = base64.b64encode(f.read()).decode()

# ── HELPERS DE API ───────────────────────────────────────────────────────────
def api_get(path: str, params: dict) -> dict:
    params["access_token"] = TOKEN
    r = requests.get(f"{BASE_URL}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_insights(account_id: str, date_preset: str, fields: list, level="account") -> dict:
    """Busca insights de uma conta para um período."""
    params = {
        "date_preset": date_preset,
        "fields": ",".join(fields),
        "level": level,
    }
    data = api_get(f"{account_id}/insights", params)
    if data.get("data"):
        return data["data"][0]
    return {}


def get_daily_insights(account_id: str) -> list:
    """Busca investimento e resultados dos últimos 30 dias, dia a dia."""
    params = {
        "date_preset": "last_30d",
        "time_increment": 1,
        "fields": "spend,date_start,actions",
        "level": "account",
    }
    data = api_get(f"{account_id}/insights", params)
    return data.get("data", [])


def get_campaigns(account_id: str) -> list:
    """Lista campanhas ativas com insights."""
    params = {
        "fields": (
            "id,name,status,objective,"
            "insights.date_preset(last_30d){spend,actions,impressions,clicks,reach,cpm,ctr,cpc}"
        ),
        "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
        "limit": 20,
    }
    data = api_get(f"{account_id}/campaigns", params)
    return data.get("data", [])


def get_ads(campaign_id: str) -> list:
    """Busca anúncios de uma campanha com insights e link de prévia."""
    params = {
        "fields": (
            "id,name,status,creative{id,name},"
            "insights.date_preset(last_30d){spend,actions,ctr,cpc},"
            "preview_shareable_link"
        ),
        "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
        "limit": 10,
    }
    data = api_get(f"{campaign_id}/ads", params)
    return data.get("data", [])


# ── FUNÇÕES DE EXTRAÇÃO ──────────────────────────────────────────────────────
def extract_action(actions: list, event_type: str) -> int:
    """Extrai valor de um tipo de ação da lista de actions."""
    for a in (actions or []):
        if a.get("action_type") == event_type:
            return int(float(a.get("value", 0)))
    return 0


def fmt_brl(val: float) -> str:
    """Formata valor em reais."""
    if val >= 1000:
        return f"R$ {val:,.0f}".replace(",", ".")
    return f"R$ {val:.2f}".replace(".", ",")


def fmt_num(val: int) -> str:
    """Formata número com separador de milhar."""
    if val >= 1000:
        return f"{val:,}".replace(",", ".")
    return str(val)


def fmt_pct(val: float) -> str:
    return f"{val:.2f}%".replace(".", ",")


def safe_div(a: float, b: float, default=0.0) -> float:
    return a / b if b else default


def delta_class(pct: float) -> str:
    if pct > 0: return "up"
    if pct < 0: return "down"
    return "neutral"


def delta_label(pct: float, invert=False) -> str:
    """invert=True quando menor é melhor (CPL, CPM)."""
    arrow = "↓" if pct < 0 else "↑"
    label = f"{arrow} {abs(pct):.0f}%"
    # Se menor é melhor e caiu = bom
    if invert:
        cls = "up" if pct < 0 else "down"
    else:
        cls = "up" if pct > 0 else "down"
    return cls, label


# ── GERAÇÃO DO HTML ──────────────────────────────────────────────────────────
def build_kcard(label: str, value: str, delta_cls: str, delta_txt: str, color: str = "") -> str:
    color_cls = f" {color}" if color else ""
    return f"""
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">{label}</div>
      <div class="kcard-value{color_cls}">{value}</div>
      <span class="kcard-delta {delta_cls}">{delta_txt}</span>
    </div>"""


def build_camp_block(camp: dict, idx: int, result_label: str, result_event: str) -> str:
    ins    = (camp.get("insights") or {}).get("data", [{}])[0]
    spend  = float(ins.get("spend", 0))
    acts   = ins.get("actions", [])
    res    = extract_action(acts, result_event)
    cpl    = safe_div(spend, res)
    name   = camp.get("name", "—")
    obj    = camp.get("objective", "—").replace("_", " ").title()

    # Busca os anúncios da campanha
    ads = get_ads(camp["id"])
    ads_sorted = sorted(
        ads,
        key=lambda a: extract_action(
            (a.get("insights") or {}).get("data", [{}])[0].get("actions", []),
            result_event
        ),
        reverse=True
    )[:3]

    creat_cards = ""
    for i, ad in enumerate(ads_sorted):
        ad_ins   = (ad.get("insights") or {}).get("data", [{}])[0]
        ad_spend = float(ad_ins.get("spend", 0))
        ad_res   = extract_action(ad_ins.get("actions", []), result_event)
        ad_cpl   = safe_div(ad_spend, ad_res)
        ad_name  = ad.get("name", "—")
        preview  = ad.get("preview_shareable_link", "#")
        tag_type = "Vídeo" if "video" in ad_name.lower() or "vsl" in ad_name.lower() or "reels" in ad_name.lower() else "Imagem"
        tag_cls  = "creat-tag-video" if tag_type == "Vídeo" else "creat-tag-image"
        cpl_color = "green" if ad_cpl < cpl * 0.9 else ("red" if ad_cpl > cpl * 1.2 else "")
        thumb_icon = "🎬" if tag_type == "Vídeo" else "🖼️"

        creat_cards += f"""
        <div class="creat-card">
          <div class="creat-rank">
            <div class="creat-num">{i+1}</div>
            <a href="{preview}" target="_blank" class="creat-name-link">{ad_name}</a>
          </div>
          <span class="creat-tag {tag_cls}">{tag_type}</span>
          <div class="creat-metrics">
            <div class="creat-m"><div class="creat-m-val {'gold' if i==0 else ''}">{fmt_num(ad_res)}</div><div class="creat-m-lbl">{result_label[:10]}</div></div>
            <div class="creat-m"><div class="creat-m-val">{fmt_brl(ad_spend)}</div><div class="creat-m-lbl">Invest.</div></div>
            <div class="creat-m"><div class="creat-m-val {cpl_color}">{fmt_brl(ad_cpl)}</div><div class="creat-m-lbl">CPL</div></div>
          </div>
          <div class="preview-btns">
            <a href="{preview}" target="_blank" class="preview-btn">▶ Ver prévia</a>
          </div>
        </div>"""

    cpl_color = "green" if cpl < 25 else ""

    return f"""
  <div class="camp-block">
    <div class="camp-hdr">
      <div class="camp-num">{idx}</div>
      <div class="camp-name">{name}</div>
      <span class="badge">{obj}</span>
    </div>
    <div class="camp-kpis">
      <div class="camp-kpi">
        <div class="camp-kpi-label">Objetivo</div>
        <div class="camp-kpi-val" style="font-size:13px;color:var(--text)">{obj}</div>
      </div>
      <div class="camp-kpi">
        <div class="camp-kpi-label">{result_label}</div>
        <div class="camp-kpi-val gold">{fmt_num(res)}</div>
      </div>
      <div class="camp-kpi">
        <div class="camp-kpi-label">Valor Investido</div>
        <div class="camp-kpi-val">{fmt_brl(spend)}</div>
      </div>
      <div class="camp-kpi">
        <div class="camp-kpi-label">CPL</div>
        <div class="camp-kpi-val {cpl_color}">{fmt_brl(cpl)}</div>
      </div>
    </div>
    <div class="creat-sec">
      <div class="creat-sec-title">🏆 Top Criativos</div>
      <div class="creat-grid">{creat_cards}</div>
    </div>
  </div>"""


def build_all_ads_rows(campaigns: list, result_label: str, result_event: str) -> str:
    all_ads = []
    for camp in campaigns:
        ads = get_ads(camp["id"])
        for ad in ads:
            ad_ins   = (ad.get("insights") or {}).get("data", [{}])[0]
            ad_spend = float(ad_ins.get("spend", 0))
            ad_res   = extract_action(ad_ins.get("actions", []), result_event)
            ad_cpl   = safe_div(ad_spend, ad_res)
            ad_ctr   = float(ad_ins.get("ctr", 0))
            preview  = ad.get("preview_shareable_link", "#")
            tag_type = "Vídeo" if "video" in ad["name"].lower() or "vsl" in ad["name"].lower() else "Imagem"
            thumb    = "🎬" if tag_type == "Vídeo" else "🖼️"
            all_ads.append({
                "name": ad["name"], "spend": ad_spend, "res": ad_res,
                "cpl": ad_cpl, "ctr": ad_ctr, "preview": preview,
                "camp_name": camp["name"], "thumb": thumb, "tag": tag_type
            })

    all_ads.sort(key=lambda x: x["res"], reverse=True)

    rows = ""
    for a in all_ads:
        cpl_color = "style=\"color:var(--green);font-weight:700\"" if a["cpl"] < 20 else (
                    "style=\"color:var(--red);font-weight:700\"" if a["cpl"] > 30 else "style=\"font-weight:700\"")
        rows += f"""
    <div class="ct-row">
      <div class="ct-td ct-creative">
        <div class="ct-thumb">{a["thumb"]}</div>
        <div class="ct-info">
          <a href="{a["preview"]}" target="_blank" class="ct-cname">{a["name"]}</a>
          <div class="ct-camp-tag">{a["camp_name"][:40]} · {a["tag"]}</div>
        </div>
      </div>
      <div class="ct-td">{fmt_brl(a["spend"])}</div>
      <div class="ct-td" style="font-weight:700">{fmt_num(a["res"])}</div>
      <div class="ct-td" {cpl_color}>{fmt_brl(a["cpl"])}</div>
      <div class="ct-td">{fmt_pct(a["ctr"])}</div>
      <div class="ct-td"><a href="{a["preview"]}" target="_blank" class="preview-btn" style="width:auto;padding:4px 10px">▶ Ver</a></div>
    </div>"""
    return rows


def build_dist_js(campaigns: list, result_event: str) -> str:
    """Gera os dados JS para os gráficos de distribuição."""
    camp_labels, camp_res, camp_cpls = [], [], []
    for c in campaigns:
        ins   = (c.get("insights") or {}).get("data", [{}])[0]
        spend = float(ins.get("spend", 0))
        res   = extract_action(ins.get("actions", []), result_event)
        cpl   = safe_div(spend, res)
        short = c["name"][:30]
        camp_labels.append(short)
        camp_res.append(res)
        camp_cpls.append(round(cpl, 2))

    max_cpl = max(camp_cpls) * 1.2 if camp_cpls else 50

    hbar_camps = ""
    for i, label in enumerate(camp_labels):
        pct = int(camp_cpls[i] / max_cpl * 100) if max_cpl else 0
        color = "var(--green)" if camp_cpls[i] < 20 else ("var(--red)" if camp_cpls[i] > 35 else "var(--gold)")
        val_fmt = f"R${camp_cpls[i]:.2f}".replace(".", ",")
        hbar_camps += f"""
    hbarCpl.innerHTML += `<div class="hbar-item">
      <div class="hbar-label">{label}</div>
      <div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:{color}"><span class="hbar-val">{val_fmt}</span></div></div>
    </div>`;"""

    labels_json  = json.dumps(camp_labels, ensure_ascii=False)
    res_json     = json.dumps(camp_res)

    return f"""
  new Chart(document.getElementById('chartDonut'), {{
    type:'doughnut',
    data:{{
      labels:{labels_json},
      datasets:[{{ data:{res_json}, backgroundColor:['#F5A623','#3b82f6','#22c55e','#a855f7','#ef4444'], borderWidth:0, hoverOffset:6 }}]
    }},
    options:{{ responsive:true, maintainAspectRatio:false, cutout:'62%',
      plugins:{{ legend:{{ position:'bottom', labels:{{ color:'#888', font:{{size:11}}, padding:12, boxWidth:8, boxHeight:8 }} }} }}
    }}
  }});
  const hbarCpl = document.getElementById('hbarCpl');
  {hbar_camps}"""


def build_daily_js(daily_data: list, result_event: str) -> str:
    """Gera arrays JS para o gráfico de evolução diária."""
    dias, invest, leads = [], [], []
    for d in sorted(daily_data, key=lambda x: x["date_start"]):
        dt = datetime.datetime.strptime(d["date_start"], "%Y-%m-%d")
        dias.append(dt.strftime("%d/%m"))
        invest.append(round(float(d.get("spend", 0)), 2))
        leads.append(extract_action(d.get("actions", []), result_event))

    return f"""
  const dias = {json.dumps(dias)};
  const investData = {json.dumps(invest)};
  const leadsData  = {json.dumps(leads)};"""


# ── TEMPLATE HTML ────────────────────────────────────────────────────────────
def render_html(account: dict, metrics: dict, campaigns: list, daily_data: list) -> str:
    client_name  = account["name"]
    niche        = account.get("niche", "")
    result_label = account.get("result_label", "Resultados")
    result_event = account.get("result_event", "lead")
    now          = datetime.datetime.now().strftime("%d/%m · %H:%M")

    # KPIs principais
    spend      = metrics.get("spend", 0)
    results    = metrics.get("results", 0)
    cpl        = safe_div(spend, results)
    msgs       = metrics.get("msgs", 0)
    cost_msg   = safe_div(spend, msgs)
    reach      = metrics.get("reach", 0)
    impressions= metrics.get("impressions", 0)
    freq       = safe_div(impressions, reach)
    cpm        = metrics.get("cpm", 0)
    clicks     = metrics.get("clicks", 0)
    ctr        = metrics.get("ctr", 0)
    cpc        = metrics.get("cpc", 0)
    video_views= metrics.get("video_views", 0)
    thruplays  = metrics.get("thruplays", 0)

    camp_blocks = ""
    for i, c in enumerate(campaigns, 1):
        camp_blocks += build_camp_block(c, i, result_label, result_event)

    all_ads_rows = build_all_ads_rows(campaigns, result_label, result_event)
    dist_js      = build_dist_js(campaigns, result_event)
    daily_js     = build_daily_js(daily_data, result_event)
    logo_src     = f"data:image/png;base64,{LOGO_B64}" if LOGO_B64 else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — {client_name} · A2 Digital</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --gold:#F5A623;--gold-dim:rgba(245,166,35,0.15);--gold-border:rgba(245,166,35,0.3);
  --bg:#0a0a0a;--surf:#111111;--surf2:#181818;--surf3:#202020;
  --border:#222222;--border2:#2a2a2a;
  --text:#efefef;--muted:#888;--dim:#444;
  --green:#22c55e;--green-dim:rgba(34,197,94,0.12);
  --red:#ef4444;--red-dim:rgba(239,68,68,0.12);
  --blue:#3b82f6;--blue-dim:rgba(59,130,246,0.12);
}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;min-height:100vh}}
.nav{{position:fixed;top:0;left:0;right:0;z-index:200;background:rgba(10,10,10,0.96);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 28px;gap:16px}}
.nav-left{{display:flex;align-items:center;gap:14px;flex-shrink:0}}
.nav-logo{{height:30px}}
.nav-divider{{width:1px;height:22px;background:var(--border2)}}
.nav-client{{font-size:14px;font-weight:600;color:var(--text);white-space:nowrap}}
.nav-tabs{{display:flex;gap:2px}}
.nav-tab{{padding:6px 14px;border:none;background:transparent;color:var(--muted);font-size:13px;font-weight:500;cursor:pointer;border-radius:6px;transition:all .15s;white-space:nowrap;font-family:inherit}}
.nav-tab:hover{{color:var(--text);background:var(--surf2)}}
.nav-tab.active{{background:var(--gold);color:#000;font-weight:700}}
.nav-right{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
.updated-pill{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);padding:4px 10px;background:var(--surf2);border:1px solid var(--border2);border-radius:20px;white-space:nowrap}}
.updated-dot{{width:6px;height:6px;border-radius:50%;background:var(--green)}}
.period-bar{{position:fixed;top:54px;left:0;right:0;z-index:190;background:var(--surf);border-bottom:1px solid var(--border);padding:8px 28px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.period-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);white-space:nowrap}}
.period-btns{{display:flex;gap:3px;flex-wrap:wrap}}
.pbtn{{padding:5px 11px;border:1px solid var(--border2);background:transparent;color:var(--muted);font-size:11px;font-weight:500;cursor:pointer;border-radius:5px;transition:all .15s;white-space:nowrap;font-family:inherit}}
.pbtn:hover{{border-color:var(--gold-border);color:var(--text)}}
.pbtn.active{{background:var(--gold);border-color:var(--gold);color:#000;font-weight:700}}
.custom-wrap{{display:none;align-items:center;gap:6px}}
.custom-wrap.show{{display:flex}}
.date-inp{{background:var(--surf2);border:1px solid var(--border2);border-radius:5px;color:var(--text);font-size:11px;padding:4px 8px;font-family:inherit}}
.date-apply{{padding:5px 12px;background:var(--gold);border:none;border-radius:5px;color:#000;font-weight:700;font-size:11px;cursor:pointer;font-family:inherit}}
.page{{display:none;padding-top:102px;min-height:100vh}}
.page.active{{display:block}}
.page-inner{{max-width:1200px;margin:0 auto;padding:32px 28px 80px}}
.sec-title{{display:flex;align-items:center;gap:10px;margin-bottom:18px;margin-top:36px}}
.sec-title:first-child{{margin-top:0}}
.sec-title h3{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--gold);white-space:nowrap}}
.sec-line{{flex:1;height:1px;background:linear-gradient(to right,var(--border2),transparent)}}
.kpi-grid{{display:grid;gap:10px}}
.kpi-grid-5{{grid-template-columns:repeat(5,1fr)}}
.kpi-grid-4{{grid-template-columns:repeat(4,1fr)}}
.kcard{{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:18px 16px 14px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s}}
.kcard:hover{{border-color:var(--border2);transform:translateY(-1px)}}
.kcard-accent{{position:absolute;top:0;left:0;right:0;height:2px;background:var(--gold);opacity:0;transition:opacity .2s}}
.kcard:hover .kcard-accent{{opacity:1}}
.kcard-label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:8px}}
.kcard-value{{font-size:24px;font-weight:800;color:var(--text);line-height:1;letter-spacing:-.02em;margin-bottom:7px}}
.kcard-value.gold{{color:var(--gold)}}
.kcard-value.green{{color:var(--green)}}
.kcard-value.red{{color:var(--red)}}
.kcard-delta{{display:inline-flex;align-items:center;gap:3px;font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px}}
.kcard-delta.up{{background:var(--green-dim);color:var(--green)}}
.kcard-delta.down{{background:var(--red-dim);color:var(--red)}}
.kcard-delta.neutral{{background:var(--surf2);color:var(--muted)}}
.chart-row{{display:grid;gap:12px;margin-bottom:12px}}
.chart-row-2{{grid-template-columns:2fr 1fr}}
.chart-card{{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:20px}}
.chart-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.chart-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text)}}
.chart-legend{{display:flex;gap:12px}}
.leg-item{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}}
.leg-dot{{width:8px;height:8px;border-radius:50%}}
.chart-wrap{{position:relative;height:200px}}
.chart-wrap-sm{{position:relative;height:180px}}
.hbar-list{{display:flex;flex-direction:column;gap:10px;margin-top:4px}}
.hbar-item{{display:flex;align-items:center;gap:10px}}
.hbar-label{{font-size:12px;color:var(--muted);width:110px;text-align:right;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hbar-track{{flex:1;background:var(--surf3);border-radius:4px;height:22px;overflow:hidden}}
.hbar-fill{{height:100%;background:var(--gold);border-radius:4px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;transition:width .6s ease;min-width:40px}}
.hbar-val{{font-size:11px;font-weight:700;color:#000}}
.camp-block{{background:var(--surf);border:1px solid var(--border);border-radius:12px;margin-bottom:20px;overflow:hidden}}
.camp-hdr{{display:flex;align-items:center;gap:10px;padding:14px 20px;border-bottom:2px solid var(--gold);background:var(--surf2)}}
.camp-num{{width:28px;height:28px;border-radius:50%;background:var(--gold);color:#000;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.camp-name{{font-size:13px;font-weight:700;color:var(--text);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.badge{{font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;border:1px solid var(--gold-border);background:var(--gold-dim);color:var(--gold);white-space:nowrap;flex-shrink:0}}
.camp-kpis{{display:grid;grid-template-columns:repeat(4,1fr)}}
.camp-kpi{{padding:14px 20px;border-right:1px solid var(--border)}}
.camp-kpi:last-child{{border-right:none}}
.camp-kpi-label{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-bottom:5px}}
.camp-kpi-val{{font-size:20px;font-weight:800;color:var(--text)}}
.camp-kpi-val.gold{{color:var(--gold)}}
.camp-kpi-val.green{{color:var(--green)}}
.creat-sec{{padding:16px 20px;border-top:1px solid var(--border)}}
.creat-sec-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);margin-bottom:12px}}
.creat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.creat-card{{background:var(--surf2);border:1px solid var(--border);border-radius:8px;padding:12px;transition:border-color .15s}}
.creat-card:hover{{border-color:var(--gold-border)}}
.creat-rank{{display:flex;align-items:center;gap:6px;margin-bottom:8px}}
.creat-num{{width:20px;height:20px;border-radius:50%;background:var(--gold);color:#000;font-size:10px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.creat-name-link{{font-size:12px;font-weight:600;color:var(--text);text-decoration:none;transition:color .15s;line-height:1.3}}
.creat-name-link:hover{{color:var(--gold)}}
.creat-tag{{display:inline-block;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-bottom:8px}}
.creat-tag-video{{background:var(--blue-dim);color:var(--blue)}}
.creat-tag-image{{background:var(--gold-dim);color:var(--gold)}}
.creat-metrics{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px}}
.creat-m{{text-align:center;padding:5px 4px;background:var(--surf3);border-radius:5px}}
.creat-m-val{{font-size:12px;font-weight:800;color:var(--text)}}
.creat-m-val.green{{color:var(--green)}}
.creat-m-val.red{{color:var(--red)}}
.creat-m-val.gold{{color:var(--gold)}}
.creat-m-lbl{{font-size:9px;color:var(--dim);margin-top:1px}}
.preview-btns{{display:flex;gap:5px;margin-top:8px}}
.preview-btn{{flex:1;padding:5px 4px;border:1px solid var(--border2);background:var(--surf3);color:var(--muted);font-size:10px;font-weight:600;border-radius:5px;cursor:pointer;text-decoration:none;text-align:center;display:flex;align-items:center;justify-content:center;gap:3px;transition:all .15s;font-family:inherit}}
.preview-btn:hover{{border-color:var(--gold-border);color:var(--gold)}}
.creat-table{{background:var(--surf);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.ct-head{{display:grid;grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr;padding:11px 20px;background:var(--surf2);border-bottom:1px solid var(--border)}}
.ct-th{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--dim)}}
.ct-row{{display:grid;grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr;padding:13px 20px;border-bottom:1px solid var(--border);align-items:center;transition:background .1s}}
.ct-row:last-child{{border-bottom:none}}
.ct-row:hover{{background:var(--surf2)}}
.ct-td{{font-size:13px;color:var(--text)}}
.ct-creative{{display:flex;align-items:center;gap:8px}}
.ct-thumb{{width:34px;height:34px;border-radius:6px;background:var(--surf3);border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}}
.ct-info{{min-width:0}}
.ct-cname{{font-size:12px;font-weight:600;color:var(--text);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;transition:color .15s}}
.ct-cname:hover{{color:var(--gold)}}
.ct-camp-tag{{font-size:10px;color:var(--dim);margin-top:1px}}
.dist-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:900px){{
  .nav-tabs{{display:none}}
  .kpi-grid-5{{grid-template-columns:repeat(2,1fr)}}
  .kpi-grid-4{{grid-template-columns:repeat(2,1fr)}}
  .chart-row-2{{grid-template-columns:1fr}}
  .camp-kpis{{grid-template-columns:repeat(2,1fr)}}
  .creat-grid{{grid-template-columns:1fr 1fr}}
  .dist-grid{{grid-template-columns:1fr}}
  .ct-head,.ct-row{{grid-template-columns:2fr 1fr 1fr}}
  .ct-th:nth-child(n+4),.ct-td:nth-child(n+4){{display:none}}
}}
@media(max-width:600px){{
  .kpi-grid-5,.kpi-grid-4{{grid-template-columns:1fr 1fr}}
  .creat-grid{{grid-template-columns:1fr}}
  .period-bar{{padding:8px 14px}}
  .page-inner{{padding:24px 14px 60px}}
}}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-left">
    {"<img src='" + logo_src + "' class='nav-logo' alt='A2 Digital'>" if logo_src else "<span style='color:var(--gold);font-weight:800;font-size:16px'>A2</span>"}
    <div class="nav-divider"></div>
    <span class="nav-client">{client_name}</span>
  </div>
  <div class="nav-tabs">
    <button class="nav-tab active" onclick="showPage('geral',this)">Visão Geral</button>
    <button class="nav-tab" onclick="showPage('campanhas',this)">Campanhas</button>
    <button class="nav-tab" onclick="showPage('criativos',this)">Criativos</button>
    <button class="nav-tab" onclick="showPage('distribuicao',this)">Distribuição</button>
  </div>
  <div class="nav-right">
    <div class="updated-pill">
      <div class="updated-dot"></div>
      Atualizado {now}
    </div>
  </div>
</nav>

<div class="period-bar">
  <span class="period-label">Período</span>
  <div class="period-btns">
    <button class="pbtn" onclick="setPeriod(this,'1d')">Hoje</button>
    <button class="pbtn" onclick="setPeriod(this,'3d')">3 dias</button>
    <button class="pbtn" onclick="setPeriod(this,'7d')">7 dias</button>
    <button class="pbtn active" onclick="setPeriod(this,'30d')">30 dias</button>
    <button class="pbtn" onclick="setPeriod(this,'month')">Mês atual</button>
    <button class="pbtn" onclick="setPeriod(this,'lmonth')">Mês passado</button>
    <button class="pbtn" onclick="setPeriod(this,'year')">Este ano</button>
    <button class="pbtn" onclick="setPeriod(this,'lyear')">Ano passado</button>
    <button class="pbtn" onclick="toggleCustom(this)">📅 Personalizado</button>
  </div>
  <div class="custom-wrap" id="customWrap">
    <input type="date" class="date-inp" id="dateFrom">
    <span style="color:var(--dim);font-size:11px">até</span>
    <input type="date" class="date-inp" id="dateTo">
    <button class="date-apply" onclick="applyCustom()">Aplicar</button>
  </div>
</div>

<!-- VISÃO GERAL -->
<div id="page-geral" class="page active">
<div class="page-inner">
  <div class="sec-title"><h3>🎯 Resultados</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-5">
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Investimento</div>
      <div class="kcard-value gold">{fmt_brl(spend)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">{result_label}</div>
      <div class="kcard-value">{fmt_num(results)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">CPL</div>
      <div class="kcard-value {'green' if cpl < 30 else 'red'}">{fmt_brl(cpl)}</div>
      <span class="kcard-delta neutral">custo por resultado</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Msgs Iniciadas</div>
      <div class="kcard-value">{fmt_num(msgs)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Custo/Mensagem</div>
      <div class="kcard-value">{fmt_brl(cost_msg)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
  </div>

  <div class="sec-title"><h3>📡 Alcance & Entrega</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-4">
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Alcance</div>
      <div class="kcard-value">{fmt_num(reach)}</div>
      <span class="kcard-delta neutral">pessoas únicas</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Impressões</div>
      <div class="kcard-value">{fmt_num(impressions)}</div>
      <span class="kcard-delta neutral">exibições totais</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Frequência</div>
      <div class="kcard-value {'red' if freq > 3 else ''}">{fmt_pct(freq)}</div>
      <span class="kcard-delta {'down' if freq > 3 else 'neutral'}">{'⚠ frequência alta' if freq > 3 else 'impressões/pessoa'}</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">CPM</div>
      <div class="kcard-value">{fmt_brl(cpm)}</div>
      <span class="kcard-delta neutral">custo por mil imp.</span>
    </div>
  </div>

  <div class="sec-title"><h3>👆 Engajamento</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-5">
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Cliques no Link</div>
      <div class="kcard-value">{fmt_num(clicks)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">CTR</div>
      <div class="kcard-value {'green' if ctr > 1.5 else ''}">{fmt_pct(ctr)}</div>
      <span class="kcard-delta {'up' if ctr > 1.5 else 'neutral'}">taxa de clique</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">CPC Médio</div>
      <div class="kcard-value green">{fmt_brl(cpc)}</div>
      <span class="kcard-delta neutral">custo por clique</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">Visualiz. Vídeo</div>
      <div class="kcard-value">{fmt_num(video_views)}</div>
      <span class="kcard-delta neutral">últimos 30d</span>
    </div>
    <div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">ThruPlay (95%+)</div>
      <div class="kcard-value">{fmt_num(thruplays)}</div>
      <span class="kcard-delta neutral">assistiram até o fim</span>
    </div>
  </div>

  <div class="sec-title"><h3>📈 Evolução Diária</h3><div class="sec-line"></div></div>
  <div class="chart-row chart-row-2">
    <div class="chart-card">
      <div class="chart-head">
        <span class="chart-title">Investimento × {result_label}</span>
        <div class="chart-legend">
          <div class="leg-item"><div class="leg-dot" style="background:var(--gold)"></div>Investimento</div>
          <div class="leg-item"><div class="leg-dot" style="background:var(--green)"></div>{result_label}</div>
        </div>
      </div>
      <div class="chart-wrap"><canvas id="chartEvolucao"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Mix de Resultados</span></div>
      <div class="chart-wrap"><canvas id="chartMix"></canvas></div>
    </div>
  </div>
</div>
</div>

<!-- CAMPANHAS -->
<div id="page-campanhas" class="page">
<div class="page-inner">
  <div class="sec-title"><h3>📣 Campanhas</h3><div class="sec-line"></div><span class="badge">{len(campaigns)} campanhas</span></div>
  {camp_blocks}
</div>
</div>

<!-- CRIATIVOS -->
<div id="page-criativos" class="page">
<div class="page-inner">
  <div class="sec-title"><h3>🎨 Ranking de Criativos</h3><div class="sec-line"></div></div>
  <div class="creat-table">
    <div class="ct-head">
      <div class="ct-th">Criativo</div>
      <div class="ct-th">Invest.</div>
      <div class="ct-th">Resultados</div>
      <div class="ct-th">CPL</div>
      <div class="ct-th">CTR</div>
      <div class="ct-th">Prévia</div>
    </div>
    {all_ads_rows}
  </div>
</div>
</div>

<!-- DISTRIBUIÇÃO -->
<div id="page-distribuicao" class="page">
<div class="page-inner">
  <div class="sec-title"><h3>📊 Distribuição por Campanha</h3><div class="sec-line"></div></div>
  <div class="dist-grid">
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">{result_label} por Campanha</span></div>
      <div class="chart-wrap-sm"><canvas id="chartDonut"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">CPL por Campanha</span></div>
      <div style="padding:8px 0"><div class="hbar-list" id="hbarCpl"></div></div>
    </div>
  </div>
</div>
</div>

<script>
function showPage(id,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(btn) btn.classList.add('active');
  if(id==='distribuicao') renderDist();
}}
function setPeriod(btn,p){{
  document.querySelectorAll('.pbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('customWrap').classList.remove('show');
}}
function toggleCustom(btn){{
  document.querySelectorAll('.pbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('customWrap').classList.toggle('show');
}}
function applyCustom(){{
  const f=document.getElementById('dateFrom').value;
  const t=document.getElementById('dateTo').value;
  if(f&&t) document.getElementById('customWrap').classList.remove('show');
}}
Chart.defaults.color='#666';
Chart.defaults.borderColor='#222';
Chart.defaults.font.family='Inter';
{daily_js}
new Chart(document.getElementById('chartEvolucao'),{{
  type:'line',
  data:{{
    labels:dias,
    datasets:[
      {{label:'Investimento',data:investData,borderColor:'#F5A623',backgroundColor:'rgba(245,166,35,.07)',tension:.4,fill:true,pointRadius:3,pointBackgroundColor:'#F5A623',yAxisID:'y'}},
      {{label:'{result_label}',data:leadsData,borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.07)',tension:.4,fill:true,pointRadius:3,pointBackgroundColor:'#22c55e',yAxisID:'y1'}}
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},
    plugins:{{legend:{{display:false}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,.04)'}},ticks:{{color:'#555',font:{{size:10}}}}}},
      y:{{position:'left',grid:{{color:'rgba(255,255,255,.04)'}},ticks:{{color:'#F5A623',font:{{size:10}},callback:v=>'R$'+v}}}},
      y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{color:'#22c55e',font:{{size:10}}}}}}
    }}
  }}
}});
new Chart(document.getElementById('chartMix'),{{
  type:'doughnut',
  data:{{
    labels:['{result_label}','Msgs Iniciadas','Cliques s/ conv.'],
    datasets:[{{data:[{results},{msgs},{max(0, clicks - results)}],backgroundColor:['#22c55e','#F5A623','#2a2a2a'],borderWidth:0,hoverOffset:6}}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'68%',
    plugins:{{legend:{{position:'bottom',labels:{{color:'#666',font:{{size:10}},padding:12,boxWidth:8,boxHeight:8}}}}}}
  }}
}});
let distDone=false;
function renderDist(){{
  if(distDone) return; distDone=true;
  {dist_js}
}}
</script>
</body>
</html>"""


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Gerando dashboards para {len(ACCOUNTS)} contas...")

    for account in ACCOUNTS:
        acc_id = account["id"]
        slug   = account["slug"]
        result_event = account.get("result_event", "lead")
        print(f"  → {account['name']} ({acc_id})")

        # Campos de insights
        fields = [
            "spend", "reach", "impressions", "clicks", "ctr", "cpc", "cpm",
            "actions", "video_p95_watched_actions"
        ]

        try:
            ins = get_insights(acc_id, "last_30d", fields)
            acts = ins.get("actions", [])

            metrics = {
                "spend":       float(ins.get("spend", 0)),
                "reach":       int(float(ins.get("reach", 0))),
                "impressions": int(float(ins.get("impressions", 0))),
                "clicks":      int(float(ins.get("clicks", 0))),
                "ctr":         float(ins.get("ctr", 0)),
                "cpc":         float(ins.get("cpc", 0)),
                "cpm":         float(ins.get("cpm", 0)),
                "results":     extract_action(acts, result_event),
                "msgs":        extract_action(acts, "onsite_conversion.messaging_conversation_started_7d"),
                "video_views": extract_action(acts, "video_view"),
                "thruplays":   sum(
                    int(float(v.get("value", 0)))
                    for v in ins.get("video_p95_watched_actions", [])
                ),
            }

            campaigns  = get_campaigns(acc_id)
            daily_data = get_daily_insights(acc_id)

            html = render_html(account, metrics, campaigns, daily_data)

            out_path = OUT_DIR / f"{slug}.html"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"     ✓ salvo em docs/{slug}.html")

        except Exception as e:
            print(f"     ✗ ERRO: {e}", file=sys.stderr)

    print("Concluído!")


if __name__ == "__main__":
    main()
