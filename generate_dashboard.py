"""
A2 Digital — Dashboard Generator v2
Meta Ads + Google Ads + Consolidado + Funis por plataforma.

Secrets necessários:
  META_ACCESS_TOKEN, DASHBOARD_ACCOUNTS,
  GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID,
  GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN
"""

import os, json, sys, base64, datetime, requests
from pathlib import Path

TOKEN    = os.environ.get("META_ACCESS_TOKEN", "")
ACCOUNTS = json.loads(os.environ["DASHBOARD_ACCOUNTS"])
MCC_ID   = "9719455407"
API_VER  = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"
OUT_DIR  = Path("docs")
OUT_DIR.mkdir(exist_ok=True)

LOGO_B64 = ""
logo_path = Path("assets/logo_a2.png")
if logo_path.exists():
    with open(logo_path, "rb") as f:
        LOGO_B64 = base64.b64encode(f.read()).decode()

MSG_EVENT = "onsite_conversion.messaging_conversation_started_7d"

# ════════════════════════════════════════════════════════════════════
# META ADS API
# ════════════════════════════════════════════════════════════════════

def api_get(path, params):
    params["access_token"] = TOKEN
    r = requests.get(f"{BASE_URL}/{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def extract_action(actions, event_type):
    for a in (actions or []):
        if a.get("action_type") == event_type:
            return int(float(a.get("value", 0)))
    return 0


def extract_action_value(values, event_type):
    for a in (values or []):
        if a.get("action_type") == event_type:
            return float(a.get("value", 0))
    return 0.0


def fetch_meta(account):
    acc_id = account["meta_account_id"]
    result_event = account.get("result_event", "lead")

    fields = ["spend", "reach", "impressions", "clicks", "ctr", "cpc", "cpm",
              "actions", "action_values", "video_p95_watched_actions"]
    ins = {}
    data = api_get(f"{acc_id}/insights",
                   {"date_preset": "last_30d", "fields": ",".join(fields), "level": "account"})
    if data.get("data"):
        ins = data["data"][0]

    acts = ins.get("actions", [])
    avs  = ins.get("action_values", [])

    metrics = {
        "spend":       float(ins.get("spend", 0)),
        "reach":       int(float(ins.get("reach", 0))),
        "impressions": int(float(ins.get("impressions", 0))),
        "clicks":      int(float(ins.get("clicks", 0))),
        "ctr":         float(ins.get("ctr", 0)),
        "cpc":         float(ins.get("cpc", 0)),
        "cpm":         float(ins.get("cpm", 0)),
        "results":     extract_action(acts, result_event),
        "msgs":        extract_action(acts, MSG_EVENT),
        "lpv":         extract_action(acts, "landing_page_view"),
        "purchases":   extract_action(acts, "purchase"),
        "revenue":     extract_action_value(avs, "purchase"),
        "video_views": extract_action(acts, "video_view"),
        "thruplays":   sum(int(float(v.get("value", 0))) for v in ins.get("video_p95_watched_actions", [])),
    }

    # ── Histórico diário de 180 dias (motor de período dinâmico) ──
    today = datetime.date.today()
    since_180 = (today - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
    until_t   = today.strftime("%Y-%m-%d")
    tr180 = json.dumps({"since": since_180, "until": until_t})

    daily = []
    params = {"time_range": tr180, "time_increment": 1, "limit": 500,
              "fields": "spend,date_start,actions,action_values,clicks,impressions",
              "level": "account", "access_token": TOKEN}
    url = f"{BASE_URL}/{acc_id}/insights"
    while url:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        j = r.json()
        daily.extend(j.get("data", []))
        url = (j.get("paging") or {}).get("next")
        params = {}  # next já vem com query string completa

    # Série diária compacta para o motor JS de períodos
    daily_compact = []
    for d in sorted(daily, key=lambda x: x.get("date_start", "")):
        acts_d = d.get("actions", [])
        avs_d  = d.get("action_values", [])
        daily_compact.append({
            "d": d.get("date_start"),
            "s": round(float(d.get("spend", 0)), 2),
            "r": extract_action(acts_d, result_event),
            "m": extract_action(acts_d, MSG_EVENT),
            "p": extract_action(acts_d, "purchase"),
            "v": round(extract_action_value(avs_d, "purchase"), 2),
            "c": int(float(d.get("clicks", 0))),
            "i": int(float(d.get("impressions", 0))),
        })

    # Busca campanhas com insights 30d
    camps = api_get(f"{acc_id}/campaigns",
                    {"fields": "id,name,status,objective,"
                               "insights.date_preset(last_30d){spend,actions,action_values,impressions,clicks,reach,cpm,ctr,cpc}",
                     "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                     "limit": 20}).get("data", [])

    # Busca insights 90d separadamente e mescla
    try:
        camps_90 = api_get(f"{acc_id}/campaigns",
                           {"fields": "id,"
                                      "insights.date_preset(last_90d){spend,actions,action_values,impressions,clicks,reach,cpm,ctr,cpc}",
                            "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                            "limit": 20}).get("data", [])
        ins90_map = {camp90["id"]: camp90.get("insights") for camp90 in camps_90}
        for camp in camps:
            camp["insights_90d"] = ins90_map.get(camp["id"])
    except Exception:
        for camp in camps:
            camp["insights_90d"] = None

    # Anúncios por campanha (30d e 90d)
    for camp in camps:
        for preset in ["last_30d", "last_90d"]:
            key = "_ads" if preset == "last_30d" else "_ads_90d"
            try:
                camp[key] = api_get(f"{camp['id']}/ads",
                                    {"fields": "id,name,status,"
                                               f"insights.date_preset({preset}){{spend,actions,ctr,cpc}},"
                                               "preview_shareable_link",
                                     "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                                     "limit": 10}).get("data", [])
            except Exception:
                camp[key] = []

    return {"metrics": metrics, "campaigns": camps, "daily_compact": daily_compact}


# ════════════════════════════════════════════════════════════════════
# GOOGLE ADS API
# ════════════════════════════════════════════════════════════════════

def google_client(login_customer_id):
    from google.ads.googleads.client import GoogleAdsClient
    cfg = {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id":       os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret":   os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token":   os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": login_customer_id,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(cfg)


def fetch_google(account):
    cid   = account["google_customer_id"]
    if account.get("google_standalone"):
        login = cid
    else:
        login = account.get("google_login_customer_id", MCC_ID)
    client = google_client(login)
    ga = client.get_service("GoogleAdsService")

    # Totais 30d
    q_tot = """
        SELECT metrics.cost_micros, metrics.clicks, metrics.impressions,
               metrics.conversions, metrics.conversions_value,
               metrics.ctr, metrics.average_cpc
        FROM customer WHERE segments.date DURING LAST_30_DAYS"""
    spend = clicks = impressions = conv = conv_value = ctr = cpc = 0
    for row in ga.search(customer_id=cid, query=q_tot):
        m = row.metrics
        spend       += m.cost_micros / 1e6
        clicks      += m.clicks
        impressions += m.impressions
        conv        += m.conversions
        conv_value  += m.conversions_value
    ctr = (clicks / impressions * 100) if impressions else 0
    cpc = (spend / clicks) if clicks else 0

    metrics = {
        "spend": spend, "clicks": int(clicks), "impressions": int(impressions),
        "conversions": round(conv, 1), "conv_value": conv_value,
        "ctr": ctr, "cpc": cpc,
        "cost_per_conv": (spend / conv) if conv else 0,
    }

    # Diário — 180 dias
    goog_today = datetime.date.today()
    s180 = (goog_today - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
    tnow = goog_today.strftime("%Y-%m-%d")
    goog_daily_compact = []
    q_day = f"""
        SELECT segments.date, metrics.cost_micros, metrics.conversions,
               metrics.clicks, metrics.impressions
        FROM customer WHERE segments.date BETWEEN '{s180}' AND '{tnow}'
        ORDER BY segments.date"""
    for row in ga.search(customer_id=cid, query=q_day):
        goog_daily_compact.append({"d": row.segments.date,
                                   "s": round(row.metrics.cost_micros / 1e6, 2),
                                   "cv": round(row.metrics.conversions, 2),
                                   "c": int(row.metrics.clicks),
                                   "i": int(row.metrics.impressions)})

    # Campanhas
    camps = []
    q_camp = """
        SELECT campaign.name, campaign.status,
               metrics.cost_micros, metrics.clicks, metrics.impressions,
               metrics.conversions, metrics.ctr
        FROM campaign
        WHERE segments.date DURING LAST_30_DAYS
          AND campaign.status IN ('ENABLED','PAUSED')
        ORDER BY metrics.cost_micros DESC"""
    for row in ga.search(customer_id=cid, query=q_camp):
        c_spend = row.metrics.cost_micros / 1e6
        if c_spend <= 0:
            continue
        camps.append({
            "name": row.campaign.name,
            "spend": c_spend,
            "clicks": int(row.metrics.clicks),
            "impressions": int(row.metrics.impressions),
            "conversions": round(row.metrics.conversions, 1),
            "ctr": row.metrics.ctr * 100,
            "cost_per_conv": (c_spend / row.metrics.conversions) if row.metrics.conversions else 0,
        })

    return {"metrics": metrics, "campaigns": camps, "daily_compact": goog_daily_compact}
# ════════════════════════════════════════════════════════════════════
# FORMATAÇÃO
# ════════════════════════════════════════════════════════════════════

def fmt_brl(v):
    if v >= 1000:
        return "R$ " + f"{v:,.0f}".replace(",", ".")
    return "R$ " + f"{v:.2f}".replace(".", ",")

def fmt_num(v):
    v = int(v)
    return f"{v:,}".replace(",", ".") if v >= 1000 else str(v)

def fmt_pct(v):
    return f"{v:.2f}%".replace(".", ",")

def fmt_x(v):
    return f"{v:.2f}×".replace(".", ",")

def sdiv(a, b, d=0.0):
    return a / b if b else d


def date_ranges():
    """Retorna (atual_since, atual_until, prev_since, prev_until) como strings."""
    today = datetime.date.today()
    cs = today - datetime.timedelta(days=30)
    cu = today - datetime.timedelta(days=1)
    ps = today - datetime.timedelta(days=60)
    pu = today - datetime.timedelta(days=31)
    f = lambda d: d.strftime("%Y-%m-%d")
    return f(cs), f(cu), f(ps), f(pu)


def delta_badge(cur, prev, invert=False):
    """Retorna (classe_css, texto) comparando com o período anterior.
    invert=True quando menor é melhor (custos)."""
    if not prev or prev == 0:
        return ("neutral", "últimos 30d")
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.5:
        return ("neutral", "estável vs anterior")
    arrow = "↑" if pct > 0 else "↓"
    good = (pct < 0) if invert else (pct > 0)
    cls = "up" if good else "down"
    return (cls, f"{arrow} {abs(pct):.0f}% vs período anterior")


# ════════════════════════════════════════════════════════════════════
# CSS BASE (compartilhado)
# ════════════════════════════════════════════════════════════════════

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --gold:#F5A623;--gold-dim:rgba(245,166,35,0.15);--gold-border:rgba(245,166,35,0.3);
  --bg:#0a0a0a;--surf:#111111;--surf2:#181818;--surf3:#202020;
  --border:#222222;--border2:#2a2a2a;
  --text:#efefef;--muted:#888;--dim:#444;
  --green:#22c55e;--green-dim:rgba(34,197,94,0.12);
  --red:#ef4444;--red-dim:rgba(239,68,68,0.12);
  --blue:#3b82f6;--blue-dim:rgba(59,130,246,0.12);
}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;min-height:100vh}
.nav{position:fixed;top:0;left:0;right:0;z-index:200;background:rgba(10,10,10,0.96);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 28px;gap:16px}
.nav-left{display:flex;align-items:center;gap:14px;flex-shrink:0}
.nav-logo{height:30px}
.nav-divider{width:1px;height:22px;background:var(--border2)}
.nav-client{font-size:14px;font-weight:600;color:var(--text);white-space:nowrap}
.nav-tabs{display:flex;gap:2px;overflow-x:auto}
.nav-tab{padding:6px 14px;border:none;background:transparent;color:var(--muted);font-size:13px;font-weight:500;cursor:pointer;border-radius:6px;transition:all .15s;white-space:nowrap;font-family:inherit}
.nav-tab:hover{color:var(--text);background:var(--surf2)}
.nav-tab.active{background:var(--gold);color:#000;font-weight:700}
.nav-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.updated-pill{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);padding:4px 10px;background:var(--surf2);border:1px solid var(--border2);border-radius:20px;white-space:nowrap}
.updated-dot{width:6px;height:6px;border-radius:50%;background:var(--green)}
.page{display:none;padding-top:70px;min-height:100vh}
.page.active{display:block}
.page-inner{max-width:1200px;margin:0 auto;padding:32px 28px 80px}
.sec-title{display:flex;align-items:center;gap:10px;margin-bottom:18px;margin-top:36px}
.sec-title:first-child{margin-top:0}
.sec-title h3{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--gold);white-space:nowrap}
.sec-line{flex:1;height:1px;background:linear-gradient(to right,var(--border2),transparent)}
.kpi-grid{display:grid;gap:10px}
.kpi-grid-5{grid-template-columns:repeat(5,1fr)}
.kpi-grid-4{grid-template-columns:repeat(4,1fr)}
.kpi-grid-3{grid-template-columns:repeat(3,1fr)}
.kcard{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:18px 16px 14px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s}
.kcard:hover{border-color:var(--border2);transform:translateY(-1px)}
.kcard-accent{position:absolute;top:0;left:0;right:0;height:2px;background:var(--gold);opacity:0;transition:opacity .2s}
.kcard:hover .kcard-accent{opacity:1}
.kcard-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:8px}
.kcard-value{font-size:24px;font-weight:800;color:var(--text);line-height:1;letter-spacing:-.02em;margin-bottom:7px}
.kcard-value.gold{color:var(--gold)}
.kcard-value.green{color:var(--green)}
.kcard-value.red{color:var(--red)}
.kcard-value.blue{color:var(--blue)}
.kcard-delta{display:inline-flex;align-items:center;gap:3px;font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px}
.kcard-delta.up{background:var(--green-dim);color:var(--green)}
.kcard-delta.down{background:var(--red-dim);color:var(--red)}
.kcard-delta.neutral{background:var(--surf2);color:var(--muted)}
.chart-row{display:grid;gap:12px;margin-bottom:12px}
.chart-row-2{grid-template-columns:2fr 1fr}
.chart-card{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:20px}
.chart-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.chart-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text)}
.chart-legend{display:flex;gap:12px}
.leg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
.leg-dot{width:8px;height:8px;border-radius:50%}
.chart-wrap{position:relative;height:200px}
.chart-wrap-sm{position:relative;height:180px}
.hbar-list{display:flex;flex-direction:column;gap:10px;margin-top:4px}
.hbar-item{display:flex;align-items:center;gap:10px}
.hbar-label{font-size:12px;color:var(--muted);width:130px;text-align:right;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hbar-track{flex:1;background:var(--surf3);border-radius:4px;height:22px;overflow:hidden}
.hbar-fill{height:100%;background:var(--gold);border-radius:4px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;min-width:46px}
.hbar-val{font-size:11px;font-weight:700;color:#000}
.camp-block{background:var(--surf);border:1px solid var(--border);border-radius:12px;margin-bottom:20px;overflow:hidden}
.camp-hdr{display:flex;align-items:center;gap:10px;padding:14px 20px;border-bottom:2px solid var(--gold);background:var(--surf2)}
.camp-num{width:28px;height:28px;border-radius:50%;background:var(--gold);color:#000;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.camp-name{font-size:13px;font-weight:700;color:var(--text);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;border:1px solid var(--gold-border);background:var(--gold-dim);color:var(--gold);white-space:nowrap;flex-shrink:0}
.badge-blue{border-color:rgba(59,130,246,.3);background:var(--blue-dim);color:var(--blue)}
.badge-green{border-color:rgba(34,197,94,.3);background:var(--green-dim);color:var(--green)}
.camp-kpis{display:grid;grid-template-columns:repeat(4,1fr)}
.camp-kpi{padding:14px 20px;border-right:1px solid var(--border)}
.camp-kpi:last-child{border-right:none}
.camp-kpi-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin-bottom:5px}
.camp-kpi-val{font-size:20px;font-weight:800;color:var(--text)}
.camp-kpi-val.gold{color:var(--gold)}
.camp-kpi-val.green{color:var(--green)}
.creat-sec{padding:16px 20px;border-top:1px solid var(--border)}
.creat-sec-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);margin-bottom:12px}
.creat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.creat-card{background:var(--surf2);border:1px solid var(--border);border-radius:8px;padding:12px;transition:border-color .15s}
.creat-card:hover{border-color:var(--gold-border)}
.creat-rank{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.creat-num{width:20px;height:20px;border-radius:50%;background:var(--gold);color:#000;font-size:10px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.creat-name-link{font-size:12px;font-weight:600;color:var(--text);text-decoration:none;transition:color .15s;line-height:1.3}
.creat-name-link:hover{color:var(--gold)}
.creat-metrics{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px}
.creat-m{text-align:center;padding:5px 4px;background:var(--surf3);border-radius:5px}
.creat-m-val{font-size:12px;font-weight:800;color:var(--text)}
.creat-m-val.green{color:var(--green)}
.creat-m-val.red{color:var(--red)}
.creat-m-val.gold{color:var(--gold)}
.creat-m-lbl{font-size:9px;color:var(--dim);margin-top:1px}
.preview-btns{display:flex;gap:5px;margin-top:8px}
.preview-btn{flex:1;padding:5px 4px;border:1px solid var(--border2);background:var(--surf3);color:var(--muted);font-size:10px;font-weight:600;border-radius:5px;cursor:pointer;text-decoration:none;text-align:center;display:flex;align-items:center;justify-content:center;gap:3px;transition:all .15s;font-family:inherit}
.preview-btn:hover{border-color:var(--gold-border);color:var(--gold)}
.creat-table{background:var(--surf);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.ct-head{display:grid;grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr;padding:11px 20px;background:var(--surf2);border-bottom:1px solid var(--border)}
.ct-th{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--dim)}
.ct-row{display:grid;grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr;padding:13px 20px;border-bottom:1px solid var(--border);align-items:center;transition:background .1s}
.ct-row:last-child{border-bottom:none}
.ct-row:hover{background:var(--surf2)}
.ct-td{font-size:13px;color:var(--text)}
.ct-creative{display:flex;align-items:center;gap:8px}
.ct-thumb{width:34px;height:34px;border-radius:6px;background:var(--surf3);border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.ct-info{min-width:0}
.ct-cname{font-size:12px;font-weight:600;color:var(--text);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;transition:color .15s}
.ct-cname:hover{color:var(--gold)}
.ct-camp-tag{font-size:10px;color:var(--dim);margin-top:1px}
.dist-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.period-bar-inline{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin-bottom:24px}
.period-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);white-space:nowrap}
.period-btns{display:flex;gap:3px;flex-wrap:wrap}
.pbtn{padding:5px 11px;border:1px solid var(--border2);background:transparent;color:var(--muted);font-size:11px;font-weight:500;cursor:pointer;border-radius:5px;transition:all .15s;white-space:nowrap;font-family:inherit}
.pbtn:hover{border-color:var(--gold-border);color:var(--text)}
.pbtn.active{background:var(--gold);border-color:var(--gold);color:#000;font-weight:700}
.custom-wrap{display:none;align-items:center;gap:6px}
.custom-wrap.show{display:flex}
.date-inp{background:var(--surf2);border:1px solid var(--border2);border-radius:5px;color:var(--text);font-size:11px;padding:4px 8px;font-family:inherit;color-scheme:dark}
.date-apply{padding:5px 12px;background:var(--gold);border:none;border-radius:5px;color:#000;font-weight:700;font-size:11px;cursor:pointer;font-family:inherit}
.funil-wrap{display:flex;flex-direction:column;align-items:center;gap:0;width:100%;max-width:560px;margin:0 auto}
.funil-stage{position:relative;display:flex;align-items:center;justify-content:center;transition:transform .15s}
.funil-stage:hover{transform:scale(1.01)}
.funil-trapezio{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:14px 20px;width:100%;cursor:default;transition:filter .15s}
.funil-stage:hover .funil-trapezio{filter:brightness(1.1)}
.funil-stage-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:rgba(255,255,255,.7);margin-bottom:3px}
.funil-stage-value{font-size:22px;font-weight:800;color:#fff;line-height:1;letter-spacing:-.02em}
.funil-stage-sub{font-size:11px;color:rgba(255,255,255,.6);margin-top:3px}
.funil-arrow{display:flex;align-items:center;justify-content:center;gap:16px;padding:6px 0;width:100%}
.funil-arrow-line{flex:1;height:1px;background:var(--border2)}
.funil-conv-badge{display:flex;flex-direction:column;align-items:center;gap:1px;padding:5px 14px;background:var(--surf2);border:1px solid var(--border2);border-radius:20px;white-space:nowrap}
.funil-conv-pct{font-size:13px;font-weight:800;color:var(--gold)}
.funil-conv-label{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}
.funil-metrics-col{display:flex;flex-direction:column;gap:8px;min-width:200px}
.funil-metric-row{background:var(--surf);border:1px solid var(--border);border-radius:8px;padding:12px 16px}
.funil-metric-etapa{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);margin-bottom:4px}
.funil-metric-items{display:flex;gap:16px;flex-wrap:wrap}
.funil-metric-val{font-size:15px;font-weight:800;color:var(--text)}
.funil-metric-val.gold{color:var(--gold)}
.funil-metric-val.green{color:var(--green)}
.funil-metric-lbl{font-size:10px;color:var(--dim);margin-top:1px}
.funil-layout{display:grid;grid-template-columns:1fr 260px;gap:24px;align-items:start;margin-bottom:48px}
.funil-plat-badge{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;margin-bottom:16px}
.funil-plat-meta{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(59,130,246,.3)}
.funil-plat-google{background:var(--green-dim);color:var(--green);border:1px solid rgba(34,197,94,.3)}
.plat-split{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.plat-card{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:18px}
.plat-card-hdr{display:flex;align-items:center;gap:8px;margin-bottom:14px}
.plat-card-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.plat-rows{display:flex;flex-direction:column;gap:8px}
.plat-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)}
.plat-row:last-child{border-bottom:none}
.plat-row-label{font-size:12px;color:var(--muted)}
.plat-row-val{font-size:14px;font-weight:700;color:var(--text)}
@media(max-width:900px){
  .nav-tabs{max-width:40vw}
  .kpi-grid-5{grid-template-columns:repeat(2,1fr)}
  .kpi-grid-4{grid-template-columns:repeat(2,1fr)}
  .kpi-grid-3{grid-template-columns:repeat(2,1fr)}
  .chart-row-2{grid-template-columns:1fr}
  .camp-kpis{grid-template-columns:repeat(2,1fr)}
  .creat-grid{grid-template-columns:1fr 1fr}
  .dist-grid{grid-template-columns:1fr}
  .plat-split{grid-template-columns:1fr}
  .funil-layout{grid-template-columns:1fr}
  .ct-head,.ct-row{grid-template-columns:2fr 1fr 1fr}
  .ct-th:nth-child(n+4),.ct-td:nth-child(n+4){display:none}
}
@media(max-width:600px){
  .kpi-grid-5,.kpi-grid-4,.kpi-grid-3{grid-template-columns:1fr 1fr}
  .creat-grid{grid-template-columns:1fr}
  .page-inner{padding:24px 14px 60px}
}
"""


# ════════════════════════════════════════════════════════════════════
# COMPONENTES HTML
# ════════════════════════════════════════════════════════════════════

def kcard(label, value, sub, color="", delta_cls="neutral", vid=""):
    c = f" {color}" if color else ""
    id_v = f' id="{vid}"' if vid else ""
    id_d = f' id="{vid}-d"' if vid else ""
    return f"""<div class="kcard"><div class="kcard-accent"></div>
      <div class="kcard-label">{label}</div>
      <div class="kcard-value{c}"{id_v}>{value}</div>
      <span class="kcard-delta {delta_cls}"{id_d}>{sub}</span>
    </div>"""


def funnel_html(stages, conversions, platform, funnel_title, metrics_rows):
    """stages: [(label, value, sub)], conversions: [(pct_label, desc)] entre etapas."""
    colors = [
        ("linear-gradient(135deg,#0ea5e9,#0284c7)", "polygon(8% 0%,92% 0%,96% 100%,4% 100%)", "100%"),
        ("linear-gradient(135deg,#7c3aed,#6d28d9)", "polygon(6% 0%,94% 0%,98% 100%,2% 100%)", "88%"),
        ("linear-gradient(135deg,#F5A623,#d97706)", "polygon(5% 0%,95% 0%,99% 100%,1% 100%)", "72%"),
        ("linear-gradient(135deg,#22c55e,#16a34a)", "polygon(4% 0%,96% 0%,100% 100%,0% 100%)", "56%"),
        ("linear-gradient(135deg,#ec4899,#db2777)", "polygon(3% 0%,97% 0%,100% 100%,0% 100%)", "44%"),
    ]
    plat_cls = "funil-plat-meta" if platform == "meta" else "funil-plat-google"
    plat_txt = "● Meta Ads" if platform == "meta" else "● Google Ads"

    body = ""
    for i, (label, value, sub) in enumerate(stages):
        bg, clip, width = colors[min(i, len(colors)-1)]
        body += f"""
        <div class="funil-stage" style="width:{width}">
          <div class="funil-trapezio" style="background:{bg};clip-path:{clip}">
            <div class="funil-stage-label">{label}</div>
            <div class="funil-stage-value">{value}</div>
            <div class="funil-stage-sub">{sub}</div>
          </div>
        </div>"""
        if i < len(conversions):
            pct, desc = conversions[i]
            body += f"""
        <div class="funil-arrow">
          <div class="funil-arrow-line"></div>
          <div class="funil-conv-badge">
            <span class="funil-conv-pct">{pct}</span>
            <span class="funil-conv-label">{desc}</span>
          </div>
          <div class="funil-arrow-line"></div>
        </div>"""

    metrics_html = ""
    for etapa, items in metrics_rows:
        items_html = "".join(
            f"""<div><div class="funil-metric-val {cls}">{val}</div><div class="funil-metric-lbl">{lbl}</div></div>"""
            for val, lbl, cls in items)
        metrics_html += f"""
      <div class="funil-metric-row">
        <div class="funil-metric-etapa">{etapa}</div>
        <div class="funil-metric-items">{items_html}</div>
      </div>"""

    return f"""
  <div class="sec-title"><h3>🔽 {funnel_title}</h3><div class="sec-line"></div></div>
  <div class="funil-layout">
    <div>
      <div style="text-align:center;margin-bottom:20px">
        <span class="funil-plat-badge {plat_cls}">{plat_txt}</span>
      </div>
      <div class="funil-wrap">{body}</div>
    </div>
    <div class="funil-metrics-col">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);margin-bottom:4px">Métricas por Etapa</div>
      {metrics_html}
    </div>
  </div>"""


def build_meta_funnel(account, m):
    """Monta o funil Meta de acordo com o tipo de resultado da conta."""
    spend = m["spend"]
    revt  = account.get("result_event", "lead")

    if revt == "purchase":
        roas = sdiv(m["revenue"], spend)
        stages = [
            ("Alcance", fmt_num(m["reach"]), "pessoas únicas"),
            ("Cliques no Link", fmt_num(m["clicks"]), f"CTR {fmt_pct(m['ctr'])}"),
            ("Visualização da Página", fmt_num(m["lpv"]), "página de compra"),
            ("Compras", fmt_num(m["purchases"]), f"receita {fmt_brl(m['revenue'])}"),
        ]
        convs = [
            (fmt_pct(sdiv(m["clicks"], m["reach"]) * 100), "clicaram"),
            (fmt_pct(sdiv(m["lpv"], m["clicks"]) * 100), "carregaram a página"),
            (fmt_pct(sdiv(m["purchases"], m["lpv"]) * 100), "compraram"),
        ]
        mrows = [
            ("Etapa 1 — Entrega", [(fmt_num(m["reach"]), "Alcance", ""), (fmt_num(m["impressions"]), "Impressões", ""), (fmt_brl(m["cpm"]), "CPM", "")]),
            ("Etapa 2 — Engajamento", [(fmt_pct(m["ctr"]), "CTR", "green" if m["ctr"] > 1.5 else ""), (fmt_num(m["clicks"]), "Cliques", ""), (fmt_brl(m["cpc"]), "CPC", "")]),
            ("Etapa 3 — Página", [(fmt_num(m["lpv"]), "Visualizações", ""), (fmt_pct(sdiv(m["lpv"], m["clicks"]) * 100), "Conexão", "")]),
            ("Etapa 4 — Venda", [(fmt_num(m["purchases"]), "Compras", "gold"), (fmt_brl(m["revenue"]), "Receita", "green"), (fmt_x(roas), "ROAS", "green" if roas >= 2 else "")]),
        ]
        return funnel_html(stages, convs, "meta", "Funil de Vendas — Meta Ads", mrows)

    elif revt == MSG_EVENT:
        cost_msg = sdiv(spend, m["msgs"])
        stages = [
            ("Alcance", fmt_num(m["reach"]), "pessoas únicas"),
            ("Cliques no Link", fmt_num(m["clicks"]), f"CTR {fmt_pct(m['ctr'])}"),
            ("Mensagens Iniciadas", fmt_num(m["msgs"]), "conversas abertas"),
            ("Custo por Mensagem", fmt_brl(cost_msg), "por conversa iniciada"),
        ]
        convs = [
            (fmt_pct(sdiv(m["clicks"], m["reach"]) * 100), "clicaram"),
            (fmt_pct(sdiv(m["msgs"], m["clicks"]) * 100), "enviaram msg"),
            ("custo", "por mensagem"),
        ]
        mrows = [
            ("Etapa 1 — Entrega", [(fmt_num(m["reach"]), "Alcance", ""), (fmt_num(m["impressions"]), "Impressões", ""), (fmt_brl(m["cpm"]), "CPM", "")]),
            ("Etapa 2 — Engajamento", [(fmt_pct(m["ctr"]), "CTR", "green" if m["ctr"] > 1.5 else ""), (fmt_num(m["clicks"]), "Cliques", ""), (fmt_brl(m["cpc"]), "CPC", "")]),
            ("Etapa 3 — Conversão", [(fmt_num(m["msgs"]), "Mensagens", "gold"), (fmt_pct(sdiv(m["msgs"], m["clicks"]) * 100), "Conv. Clique→Msg", "")]),
            ("Etapa 4 — Custo", [(fmt_brl(cost_msg), "Custo/Mensagem", "green"), (fmt_brl(spend), "Investimento", "gold")]),
        ]
        return funnel_html(stages, convs, "meta", "Funil de Mensagens — Meta Ads", mrows)

    else:  # leads
        cpl = sdiv(spend, m["results"])
        stages = [
            ("Alcance", fmt_num(m["reach"]), "pessoas únicas"),
            ("Cliques no Link", fmt_num(m["clicks"]), f"CTR {fmt_pct(m['ctr'])}"),
            ("Leads", fmt_num(m["results"]), "cadastros gerados"),
            ("Custo por Lead", fmt_brl(cpl), "por lead gerado"),
        ]
        convs = [
            (fmt_pct(sdiv(m["clicks"], m["reach"]) * 100), "clicaram"),
            (fmt_pct(sdiv(m["results"], m["clicks"]) * 100), "viraram lead"),
            ("custo", "por lead"),
        ]
        mrows = [
            ("Etapa 1 — Entrega", [(fmt_num(m["reach"]), "Alcance", ""), (fmt_num(m["impressions"]), "Impressões", ""), (fmt_brl(m["cpm"]), "CPM", "")]),
            ("Etapa 2 — Engajamento", [(fmt_pct(m["ctr"]), "CTR", "green" if m["ctr"] > 1.5 else ""), (fmt_num(m["clicks"]), "Cliques", ""), (fmt_brl(m["cpc"]), "CPC", "")]),
            ("Etapa 3 — Conversão", [(fmt_num(m["results"]), "Leads", "gold"), (fmt_pct(sdiv(m["results"], m["clicks"]) * 100), "Conv. Clique→Lead", "")]),
            ("Etapa 4 — Custo", [(fmt_brl(cpl), "CPL", "green"), (fmt_brl(spend), "Investimento", "gold")]),
        ]
        return funnel_html(stages, convs, "meta", "Funil de Leads — Meta Ads", mrows)


def build_google_funnel(g):
    m = g["metrics"]
    stages = [
        ("Impressões", fmt_num(m["impressions"]), "exibições na busca/rede"),
        ("Cliques", fmt_num(m["clicks"]), f"CTR {fmt_pct(m['ctr'])}"),
        ("Conversões", str(m["conversions"]).replace(".", ","), "ações concluídas"),
        ("Custo por Conversão", fmt_brl(m["cost_per_conv"]), "por conversão"),
    ]
    convs = [
        (fmt_pct(m["ctr"]), "clicaram"),
        (fmt_pct(sdiv(m["conversions"], m["clicks"]) * 100), "converteram"),
        ("custo", "por conversão"),
    ]
    mrows = [
        ("Etapa 1 — Entrega", [(fmt_num(m["impressions"]), "Impressões", "")]),
        ("Etapa 2 — Engajamento", [(fmt_pct(m["ctr"]), "CTR", "green" if m["ctr"] > 3 else ""), (fmt_num(m["clicks"]), "Cliques", ""), (fmt_brl(m["cpc"]), "CPC", "")]),
        ("Etapa 3 — Conversão", [(str(m["conversions"]).replace(".", ","), "Conversões", "gold"), (fmt_pct(sdiv(m["conversions"], m["clicks"]) * 100), "Taxa de Conv.", "")]),
        ("Etapa 4 — Custo", [(fmt_brl(m["cost_per_conv"]), "Custo/Conv.", "green"), (fmt_brl(m["spend"]), "Investimento", "gold")]),
    ]
    return funnel_html(stages, convs, "google", "Funil de Conversão — Google Ads", mrows)


# ════════════════════════════════════════════════════════════════════
# PÁGINAS
# ════════════════════════════════════════════════════════════════════

def page_meta_overview(account, meta, page_id, title):
    m = meta["metrics"]
    result_label = account.get("result_label", "Resultados")
    cpl = sdiv(m["spend"], m["results"])
    has_roas = account.get("has_roas", False)

    cards1 = kcard("Investimento", fmt_brl(m["spend"]), "", "gold", vid="mSpend")
    cards1 += kcard(result_label, fmt_num(m["results"]), "", vid="mResults")
    cards1 += kcard("Custo por Resultado", fmt_brl(cpl), "",
                    "green" if cpl < 30 else "", vid="mCpl")
    if has_roas:
        roas = sdiv(m["revenue"], m["spend"])
        cards1 += kcard("Receita", fmt_brl(m["revenue"]), "", "green", vid="mRev")
        cards1 += kcard("ROAS", fmt_x(roas), "", "green" if roas >= 2 else "red", vid="mRoas")
    else:
        cards1 += kcard("Msgs Iniciadas", fmt_num(m["msgs"]), "", vid="mMsgs")
        cards1 += kcard("Custo/Mensagem", fmt_brl(sdiv(m["spend"], m["msgs"])), "", vid="mCostMsg")

    freq = sdiv(m["impressions"], m["reach"])
    cards2 = kcard("Alcance", fmt_num(m["reach"]), "últimos 30d (fixo)")
    cards2 += kcard("Impressões", fmt_num(m["impressions"]), "", vid="mImp")
    cards2 += kcard("Frequência", fmt_x(freq), "últimos 30d (fixo)", "red" if freq > 3 else "")
    cards2 += kcard("CPM", fmt_brl(m["cpm"]), "", vid="mCpm")

    cards3 = kcard("Cliques no Link", fmt_num(m["clicks"]), "", vid="mClicks")
    cards3 += kcard("CTR", fmt_pct(m["ctr"]), "", "green" if m["ctr"] > 1.5 else "", vid="mCtr")
    cards3 += kcard("CPC Médio", fmt_brl(m["cpc"]), "", "green", vid="mCpc")
    cards3 += kcard("Visualiz. Vídeo", fmt_num(m["video_views"]), "últimos 30d (fixo)")
    cards3 += kcard("ThruPlay (95%+)", fmt_num(m["thruplays"]), "últimos 30d (fixo)")

    return f"""
<div id="page-{page_id}" class="page">
<div class="page-inner">
  <div class="period-bar-inline">
    <span class="period-label">Período</span>
    <div class="period-btns">
      <button class="pbtn" onclick="setPeriod(this,'1d')">Hoje</button>
      <button class="pbtn" onclick="setPeriod(this,'7d')">7 dias</button>
      <button class="pbtn active" onclick="setPeriod(this,'30d')">30 dias</button>
      <button class="pbtn" onclick="setPeriod(this,'month')">Mês atual</button>
      <button class="pbtn" onclick="setPeriod(this,'lmonth')">Mês passado</button>
      <button class="pbtn" onclick="setPeriod(this,'90d')">3 meses</button>
      <button class="pbtn" onclick="setPeriod(this,'180d')">6 meses</button>
      <button class="pbtn" onclick="toggleCustom(this)">📅 Personalizado</button>
    </div>
    <div class="custom-wrap" id="customWrap">
      <input type="date" class="date-inp" id="dateFrom">
      <span style="color:var(--dim);font-size:11px">até</span>
      <input type="date" class="date-inp" id="dateTo">
      <button class="date-apply" onclick="applyCustom()">Aplicar</button>
    </div>
  </div>

  <div class="sec-title"><h3>🎯 {title} — Resultados <span id="periodTag" style="color:var(--dim);text-transform:none;letter-spacing:0">· últimos 30 dias</span></h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-5">{cards1}</div>
  <div class="sec-title"><h3>📡 Alcance & Entrega</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-4">{cards2}</div>
  <div class="sec-title"><h3>👆 Engajamento</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-5">{cards3}</div>

  <div class="sec-title"><h3>⚖️ Comparativo de Períodos</h3><div class="sec-line"></div></div>
  <div class="chart-row" style="grid-template-columns:1fr">
    <div class="chart-card">
      <div class="chart-head" style="flex-wrap:wrap;gap:10px">
        <span class="chart-title">Comparar períodos personalizados</span>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <span style="font-size:10px;color:var(--gold);font-weight:700">A</span>
          <input type="date" class="date-inp" id="cmpAFrom">
          <input type="date" class="date-inp" id="cmpATo">
          <span style="font-size:10px;color:#888;font-weight:700;margin-left:6px">B</span>
          <input type="date" class="date-inp" id="cmpBFrom">
          <input type="date" class="date-inp" id="cmpBTo">
          <button class="date-apply" onclick="applyCompare()">Comparar</button>
        </div>
      </div>
      <div id="cmpSummary" style="font-size:12px;color:var(--muted);margin-bottom:12px"></div>
      <div class="chart-wrap"><canvas id="chartCompare"></canvas></div>
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
      <div class="chart-wrap"><canvas id="chartMetaDaily"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Mix de Resultados</span></div>
      <div class="chart-wrap"><canvas id="chartMetaMix"></canvas></div>
    </div>
  </div>
</div>
</div>"""


def page_google_overview(g, page_id, title):
    m = g["metrics"]
    gp = g.get("prev", {})
    cards = kcard_cmp("Investimento", fmt_brl(m["spend"]), m["spend"], gp.get("spend"), "gold")
    cards += kcard_cmp("Conversões", str(m["conversions"]).replace(".", ","), m["conversions"], gp.get("conversions"))
    cards += kcard_cmp("Custo/Conversão", fmt_brl(m["cost_per_conv"]), m["cost_per_conv"], gp.get("cost_per_conv"),
                       "green" if m["cost_per_conv"] < 50 else "", invert=True)
    cards += kcard_cmp("Cliques", fmt_num(m["clicks"]), m["clicks"], gp.get("clicks"))
    cards += kcard_cmp("CTR", fmt_pct(m["ctr"]), m["ctr"], gp.get("ctr"), "green" if m["ctr"] > 3 else "")

    cards2 = kcard("Impressões", fmt_num(m["impressions"]), "exibições")
    cards2 += kcard("CPC Médio", fmt_brl(m["cpc"]), "custo por clique")
    if m["conv_value"] > 0:
        cards2 += kcard("Valor de Conversão", fmt_brl(m["conv_value"]), "receita atribuída", "green")
        cards2 += kcard("ROAS", fmt_x(sdiv(m["conv_value"], m["spend"])), "retorno", "green")
    else:
        cards2 += kcard("Taxa de Conversão", fmt_pct(sdiv(m["conversions"], m["clicks"]) * 100), "cliques → conversões")
        cards2 += kcard("Invest. Diário Médio", fmt_brl(m["spend"] / 30), "média 30d")

    camp_rows = ""
    for i, c in enumerate(g["campaigns"][:10], 1):
        camp_rows += f"""
    <div class="ct-row" style="grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr">
      <div class="ct-td ct-creative">
        <div class="ct-thumb">🔍</div>
        <div class="ct-info"><span class="ct-cname">{c["name"]}</span></div>
      </div>
      <div class="ct-td">{fmt_brl(c["spend"])}</div>
      <div class="ct-td" style="font-weight:700">{str(c["conversions"]).replace(".", ",")}</div>
      <div class="ct-td">{fmt_brl(c["cost_per_conv"])}</div>
      <div class="ct-td">{fmt_pct(c["ctr"])}</div>
      <div class="ct-td">{fmt_num(c["clicks"])}</div>
    </div>"""

    return f"""
<div id="page-{page_id}" class="page">
<div class="page-inner">
  <div class="sec-title"><h3>🔍 {title} — Resultados</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-5">{cards}</div>
  <div class="sec-title"><h3>📊 Desempenho</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-4">{cards2}</div>
  <div class="sec-title"><h3>📈 Evolução Diária</h3><div class="sec-line"></div></div>
  <div class="chart-row chart-row-2">
    <div class="chart-card">
      <div class="chart-head">
        <span class="chart-title">Investimento × Conversões</span>
        <div class="chart-legend">
          <div class="leg-item"><div class="leg-dot" style="background:var(--gold)"></div>Investimento</div>
          <div class="leg-item"><div class="leg-dot" style="background:var(--green)"></div>Conversões</div>
        </div>
      </div>
      <div class="chart-wrap"><canvas id="chartGoogleDaily"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Invest. por Campanha</span></div>
      <div class="chart-wrap"><canvas id="chartGoogleCampDonut"></canvas></div>
    </div>
  </div>
  <div class="sec-title"><h3>📣 Campanhas Google Ads</h3><div class="sec-line"></div></div>
  <div class="creat-table">
    <div class="ct-head" style="grid-template-columns:2.5fr 1fr 1fr 1fr 1fr 1fr">
      <div class="ct-th">Campanha</div>
      <div class="ct-th">Invest.</div>
      <div class="ct-th">Conversões</div>
      <div class="ct-th">Custo/Conv.</div>
      <div class="ct-th">CTR</div>
      <div class="ct-th">Cliques</div>
    </div>
    {camp_rows}
  </div>
</div>
</div>"""


def page_consolidado(account, meta, g):
    mm = meta["metrics"]
    gm = g["metrics"]
    total_spend   = mm["spend"] + gm["spend"]
    meta_results  = mm["results"]
    goog_results  = gm["conversions"]
    total_results = meta_results + goog_results
    blended_cost  = sdiv(total_spend, total_results)
    result_label  = account.get("result_label", "Resultados")

    cards = kcard("Investimento Total", fmt_brl(total_spend), "Meta + Google · 30d", "gold")
    cards += kcard("Resultados Totais", fmt_num(int(total_results)), f"{result_label} + conversões Google")
    cards += kcard("Custo Médio Geral", fmt_brl(blended_cost), "blended das 2 plataformas", "green" if blended_cost < 40 else "")

    pct_meta = sdiv(mm["spend"], total_spend) * 100
    pct_goog = 100 - pct_meta

    return f"""
<div id="page-consolidado" class="page active">
<div class="page-inner">
  <div class="sec-title"><h3>🌐 Visão Consolidada — Meta + Google</h3><div class="sec-line"></div></div>
  <div class="kpi-grid kpi-grid-3">{cards}</div>

  <div class="plat-split">
    <div class="plat-card">
      <div class="plat-card-hdr">
        <span class="badge badge-blue">Meta Ads</span>
        <span class="plat-card-title" style="color:var(--blue)">{fmt_pct(pct_meta)} do investimento</span>
      </div>
      <div class="plat-rows">
        <div class="plat-row"><span class="plat-row-label">Investimento</span><span class="plat-row-val">{fmt_brl(mm["spend"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">{result_label}</span><span class="plat-row-val">{fmt_num(mm["results"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">Custo por Resultado</span><span class="plat-row-val">{fmt_brl(sdiv(mm["spend"], mm["results"]))}</span></div>
        <div class="plat-row"><span class="plat-row-label">Cliques</span><span class="plat-row-val">{fmt_num(mm["clicks"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">CTR</span><span class="plat-row-val">{fmt_pct(mm["ctr"])}</span></div>
      </div>
    </div>
    <div class="plat-card">
      <div class="plat-card-hdr">
        <span class="badge badge-green">Google Ads</span>
        <span class="plat-card-title" style="color:var(--green)">{fmt_pct(pct_goog)} do investimento</span>
      </div>
      <div class="plat-rows">
        <div class="plat-row"><span class="plat-row-label">Investimento</span><span class="plat-row-val">{fmt_brl(gm["spend"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">Conversões</span><span class="plat-row-val">{str(gm["conversions"]).replace(".", ",")}</span></div>
        <div class="plat-row"><span class="plat-row-label">Custo por Conversão</span><span class="plat-row-val">{fmt_brl(gm["cost_per_conv"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">Cliques</span><span class="plat-row-val">{fmt_num(gm["clicks"])}</span></div>
        <div class="plat-row"><span class="plat-row-label">CTR</span><span class="plat-row-val">{fmt_pct(gm["ctr"])}</span></div>
      </div>
    </div>
  </div>

  <div class="sec-title"><h3>📊 Divisão do Investimento</h3><div class="sec-line"></div></div>
  <div class="chart-row chart-row-2">
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Investimento Diário Somado</span></div>
      <div class="chart-wrap"><canvas id="chartConsolidadoDaily"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Split por Plataforma</span></div>
      <div class="chart-wrap"><canvas id="chartSplit"></canvas></div>
    </div>
  </div>
</div>
</div>"""


def build_camp_blocks(campaigns, result_label, result_event, ads_key="_ads"):
    blocks = ""
    for i, camp in enumerate(campaigns, 1):
        ins   = (camp.get("insights") or {}).get("data", [{}])[0]
        spend = float(ins.get("spend", 0))
        if spend <= 0:
            continue
        res = extract_action(ins.get("actions", []), result_event)
        cpl = sdiv(spend, res)
        obj = camp.get("objective", "—").replace("OUTCOME_", "").replace("_", " ").title()

        ads_sorted = sorted(
            camp.get(ads_key, []),
            key=lambda a: extract_action((a.get("insights") or {}).get("data", [{}])[0].get("actions", []), result_event),
            reverse=True)[:3]

        creats = ""
        for j, ad in enumerate(ads_sorted):
            ai = (ad.get("insights") or {}).get("data", [{}])[0]
            a_spend = float(ai.get("spend", 0))
            a_res   = extract_action(ai.get("actions", []), result_event)
            a_cpl   = sdiv(a_spend, a_res)
            prev    = ad.get("preview_shareable_link", "#")
            cpl_cls = "green" if a_cpl and a_cpl < cpl * 0.9 else ("red" if a_cpl > cpl * 1.3 else "")
            creats += f"""
        <div class="creat-card">
          <div class="creat-rank">
            <div class="creat-num">{j+1}</div>
            <a href="{prev}" target="_blank" class="creat-name-link">{ad.get("name","—")}</a>
          </div>
          <div class="creat-metrics">
            <div class="creat-m"><div class="creat-m-val {'gold' if j==0 else ''}">{fmt_num(a_res)}</div><div class="creat-m-lbl">Resultados</div></div>
            <div class="creat-m"><div class="creat-m-val">{fmt_brl(a_spend)}</div><div class="creat-m-lbl">Invest.</div></div>
            <div class="creat-m"><div class="creat-m-val {cpl_cls}">{fmt_brl(a_cpl)}</div><div class="creat-m-lbl">Custo/Res.</div></div>
          </div>
          <div class="preview-btns">
            <a href="{prev}" target="_blank" class="preview-btn">▶ Ver prévia</a>
          </div>
        </div>"""

        blocks += f"""
  <div class="camp-block">
    <div class="camp-hdr">
      <div class="camp-num">{i}</div>
      <div class="camp-name">{camp.get("name","—")}</div>
      <span class="badge">{obj}</span>
      <span class="badge badge-blue">Meta</span>
    </div>
    <div class="camp-kpis">
      <div class="camp-kpi"><div class="camp-kpi-label">Objetivo</div><div class="camp-kpi-val" style="font-size:13px">{obj}</div></div>
      <div class="camp-kpi"><div class="camp-kpi-label">{result_label}</div><div class="camp-kpi-val gold">{fmt_num(res)}</div></div>
      <div class="camp-kpi"><div class="camp-kpi-label">Valor Investido</div><div class="camp-kpi-val">{fmt_brl(spend)}</div></div>
      <div class="camp-kpi"><div class="camp-kpi-label">Custo/Resultado</div><div class="camp-kpi-val {'green' if cpl < 25 else ''}">{fmt_brl(cpl)}</div></div>
    </div>
    <div class="creat-sec">
      <div class="creat-sec-title">🏆 Top Criativos</div>
      <div class="creat-grid">{creats if creats else '<p style="color:var(--dim);font-size:12px">Sem criativos no período.</p>'}</div>
    </div>
  </div>"""
    return blocks or '<p style="color:var(--muted)">Nenhuma campanha com investimento no período.</p>'


def page_campanhas_meta(account, meta):
    result_label = account.get("result_label", "Resultados")
    result_event = account.get("result_event", "lead")
    blocks_30 = build_camp_blocks(meta["campaigns"], result_label, result_event, "_ads")
    blocks_90 = build_camp_blocks(meta["campaigns"], result_label, result_event, "_ads_90d")

    return f"""
<div id="page-campanhas" class="page">
<div class="page-inner">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:20px">
    <div class="sec-title" style="margin:0"><h3>📣 Campanhas Meta Ads</h3></div>
    <div style="display:flex;gap:4px">
      <button class="pbtn active" onclick="switchCampPeriod(this,'30d')">Últimos 30 dias</button>
      <button class="pbtn" onclick="switchCampPeriod(this,'90d')">Últimos 3 meses</button>
    </div>
  </div>
  <div id="campBlocks30">{blocks_30}</div>
  <div id="campBlocks90" style="display:none">{blocks_90}</div>
</div>
</div>"""


def page_criativos_meta(account, meta):
    result_event = account.get("result_event", "lead")
    all_ads = []
    for c in meta["campaigns"]:
        for ad in c.get("_ads", []):
            ai = (ad.get("insights") or {}).get("data", [{}])[0]
            a_spend = float(ai.get("spend", 0))
            if a_spend <= 0:
                continue
            a_res = extract_action(ai.get("actions", []), result_event)
            all_ads.append({
                "name": ad.get("name", "—"), "spend": a_spend, "res": a_res,
                "cpl": sdiv(a_spend, a_res), "ctr": float(ai.get("ctr", 0)),
                "prev": ad.get("preview_shareable_link", "#"), "camp": c.get("name", "—"),
            })
    all_ads.sort(key=lambda x: x["res"], reverse=True)

    rows = ""
    for a in all_ads:
        cls = 'style="color:var(--green);font-weight:700"' if a["cpl"] and a["cpl"] < 20 else \
              ('style="color:var(--red);font-weight:700"' if a["cpl"] > 35 else 'style="font-weight:700"')
        rows += f"""
    <div class="ct-row">
      <div class="ct-td ct-creative">
        <div class="ct-thumb">🎨</div>
        <div class="ct-info">
          <a href="{a["prev"]}" target="_blank" class="ct-cname">{a["name"]}</a>
          <div class="ct-camp-tag">{a["camp"][:45]}</div>
        </div>
      </div>
      <div class="ct-td">{fmt_brl(a["spend"])}</div>
      <div class="ct-td" style="font-weight:700">{fmt_num(a["res"])}</div>
      <div class="ct-td" {cls}>{fmt_brl(a["cpl"])}</div>
      <div class="ct-td">{fmt_pct(a["ctr"])}</div>
      <div class="ct-td"><a href="{a["prev"]}" target="_blank" class="preview-btn" style="width:auto;padding:4px 10px">▶ Ver</a></div>
    </div>"""

    # 90d rows
    all_ads_90 = []
    for camp in meta["campaigns"]:
        for ad in camp.get("_ads_90d", []):
            ai = (ad.get("insights") or {}).get("data", [{}])[0]
            a_spend = float(ai.get("spend", 0))
            if a_spend <= 0:
                continue
            a_res = extract_action(ai.get("actions", []), result_event)
            all_ads_90.append({
                "name": ad.get("name", "—"), "spend": a_spend, "res": a_res,
                "cpl": sdiv(a_spend, a_res), "ctr": float(ai.get("ctr", 0)),
                "prev": ad.get("preview_shareable_link", "#"), "camp": camp.get("name", "—"),
            })
    all_ads_90.sort(key=lambda x: x["res"], reverse=True)

    rows_90 = ""
    for a in all_ads_90:
        cls = 'style="color:var(--green);font-weight:700"' if a["cpl"] and a["cpl"] < 20 else               ('style="color:var(--red);font-weight:700"' if a["cpl"] > 35 else 'style="font-weight:700"')
        rows_90 += f"""
    <div class="ct-row">
      <div class="ct-td ct-creative">
        <div class="ct-thumb">🎨</div>
        <div class="ct-info">
          <a href="{a["prev"]}" target="_blank" class="ct-cname">{a["name"]}</a>
          <div class="ct-camp-tag">{a["camp"][:45]}</div>
        </div>
      </div>
      <div class="ct-td">{fmt_brl(a["spend"])}</div>
      <div class="ct-td" style="font-weight:700">{fmt_num(a["res"])}</div>
      <div class="ct-td" {cls}>{fmt_brl(a["cpl"])}</div>
      <div class="ct-td">{fmt_pct(a["ctr"])}</div>
      <div class="ct-td"><a href="{a["prev"]}" target="_blank" class="preview-btn" style="width:auto;padding:4px 10px">▶ Ver</a></div>
    </div>"""

    def table_wrap(r):
        return f"""<div class="creat-table">
    <div class="ct-head">
      <div class="ct-th">Criativo</div><div class="ct-th">Invest.</div>
      <div class="ct-th">Resultados</div><div class="ct-th">Custo/Res.</div>
      <div class="ct-th">CTR</div><div class="ct-th">Prévia</div>
    </div>
    {r or '<div style="padding:20px;color:var(--muted)">Sem criativos.</div>'}
  </div>"""

    return f"""
<div id="page-criativos" class="page">
<div class="page-inner">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:20px">
    <div class="sec-title" style="margin:0"><h3>🎨 Ranking de Criativos — Meta Ads</h3></div>
    <div style="display:flex;gap:4px">
      <button class="pbtn active" onclick="switchCreatPeriod(this,'30d')">30 dias</button>
      <button class="pbtn" onclick="switchCreatPeriod(this,'90d')">3 meses</button>
    </div>
  </div>
  <div id="creatTable30">{table_wrap(rows)}</div>
  <div id="creatTable90" style="display:none">{table_wrap(rows_90)}</div>
</div>
</div>"""


def page_distribuicao_meta(account, meta):
    result_event = account.get("result_event", "lead")
    result_label = account.get("result_label", "Resultados")
    labels, values, cpls = [], [], []
    for c in meta["campaigns"]:
        ins = (c.get("insights") or {}).get("data", [{}])[0]
        spend = float(ins.get("spend", 0))
        if spend <= 0:
            continue
        res = extract_action(ins.get("actions", []), result_event)
        labels.append(c.get("name", "—")[:32])
        values.append(res)
        cpls.append(round(sdiv(spend, res), 2))

    max_cpl = max(cpls) * 1.15 if cpls else 50
    hbars = ""
    for i, lb in enumerate(labels):
        pct = int(sdiv(cpls[i], max_cpl) * 100)
        color = "var(--green)" if cpls[i] < 20 else ("var(--red)" if cpls[i] > 40 else "var(--gold)")
        val = f"R${cpls[i]:.2f}".replace(".", ",")
        hbars += f"""<div class="hbar-item">
      <div class="hbar-label">{lb}</div>
      <div class="hbar-track"><div class="hbar-fill" style="width:{pct}%;background:{color}"><span class="hbar-val">{val}</span></div></div>
    </div>"""

    return f"""
<div id="page-distribuicao" class="page">
<div class="page-inner">
  <div class="sec-title"><h3>📊 Distribuição por Campanha — Meta Ads</h3><div class="sec-line"></div></div>
  <div class="dist-grid">
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">{result_label} por Campanha</span></div>
      <div class="chart-wrap-sm"><canvas id="chartDistDonut"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-head"><span class="chart-title">Custo/Resultado por Campanha</span></div>
      <div style="padding:8px 0"><div class="hbar-list">{hbars}</div></div>
    </div>
  </div>
</div>
</div>""", labels, values


def page_funil(account, meta, g):
    parts = ""
    if meta:
        parts += build_meta_funnel(account, meta["metrics"])
    if g:
        parts += build_google_funnel(g)
    return f"""
<div id="page-funil" class="page">
<div class="page-inner">
  {parts}
</div>
</div>"""


# ════════════════════════════════════════════════════════════════════
# RENDER FINAL
# ════════════════════════════════════════════════════════════════════

def render(account, meta, g):
    name = account["name"]
    has_meta = meta is not None
    has_goog = g is not None
    dual = has_meta and has_goog
    result_label = account.get("result_label", "Resultados")
    result_event = account.get("result_event", "lead")
    now = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime("%d/%m · %H:%M")
    logo = f"data:image/png;base64,{LOGO_B64}" if LOGO_B64 else ""

    # ── TABS ──
    tabs, pages = [], ""
    if dual:
        tabs.append(("consolidado", "Consolidado"))
        tabs.append(("meta", "Meta Ads"))
        tabs.append(("google", "Google Ads"))
    elif has_meta:
        tabs.append(("meta", "Visão Geral"))
    else:
        tabs.append(("google", "Visão Geral"))

    if has_meta:
        tabs.append(("campanhas", "Campanhas"))
        tabs.append(("criativos", "Criativos"))
        tabs.append(("distribuicao", "Distribuição"))
    tabs.append(("funil", "Funil"))

    first_tab = tabs[0][0]

    # ── PAGES ──
    dist_labels, dist_values = [], []
    if dual:
        pages += page_consolidado(account, meta, g)
        pages += page_meta_overview(account, meta, "meta", "Meta Ads")
        pages += page_google_overview(g, "google", "Google Ads")
    elif has_meta:
        pages += page_meta_overview(account, meta, "meta", "Visão Geral").replace(
            '<div id="page-meta" class="page">', '<div id="page-meta" class="page active">')
    else:
        pages += page_google_overview(g, "google", "Visão Geral").replace(
            '<div id="page-google" class="page">', '<div id="page-google" class="page active">')

    if has_meta:
        pages += page_campanhas_meta(account, meta)
        pages += page_criativos_meta(account, meta)
        dist_html, dist_labels, dist_values = page_distribuicao_meta(account, meta)
        pages += dist_html

    pages += page_funil(account, meta if has_meta else None, g if has_goog else None)

    tab_btns = "".join(
        f"""<button class="nav-tab{' active' if t[0] == first_tab else ''}" onclick="showPage('{t[0]}',this)">{t[1]}</button>"""
        for t in tabs)

    # ── JS DATA ──
    js = ""
    if has_meta:
        m = meta["metrics"]
        dc = meta.get("daily_compact", [])
        js += f"""
  const DM = {json.dumps(dc)};
  const HAS_ROAS = {str(account.get("has_roas", False)).lower()};
  const RESULT_LABEL = {json.dumps(result_label)};"""

        if dist_labels:
            js += f"""
  new Chart(document.getElementById('chartDistDonut'),{{type:'doughnut',data:{{
    labels:{json.dumps(dist_labels, ensure_ascii=False)},
    datasets:[{{data:{json.dumps(dist_values)},backgroundColor:['#F5A623','#3b82f6','#22c55e','#a855f7','#ef4444','#06b6d4','#f97316'],borderWidth:0,hoverOffset:6}}]}},
    options:{{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{{legend:{{position:'bottom',labels:{{color:'#888',font:{{size:10}},padding:10,boxWidth:8,boxHeight:8}}}}}}}}}});"""

        js += """
  // ════ MOTOR DE PERÍODOS ════
  const fmtBRL = v => v >= 1000 ? 'R$ ' + Math.round(v).toLocaleString('pt-BR') : 'R$ ' + v.toFixed(2).replace('.', ',');
  const fmtNum = v => Math.round(v).toLocaleString('pt-BR');
  const fmtPct = v => v.toFixed(2).replace('.', ',') + '%';
  const fmtX   = v => v.toFixed(2).replace('.', ',') + '×';
  const dstr   = d => d.toISOString().slice(0, 10);

  function sumRange(from, to) {
    const acc = { s: 0, r: 0, m: 0, p: 0, v: 0, c: 0, i: 0 };
    for (const row of DM) {
      if (row.d >= from && row.d <= to) {
        acc.s += row.s; acc.r += row.r; acc.m += row.m;
        acc.p += row.p; acc.v += row.v; acc.c += row.c; acc.i += row.i;
      }
    }
    return acc;
  }

  function setText(id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; }

  function setDelta(id, cur, prev, invert) {
    const el = document.getElementById(id + '-d');
    if (!el) return;
    if (!prev) { el.textContent = 'sem base de comparação'; el.className = 'kcard-delta neutral'; return; }
    const pct = (cur - prev) / prev * 100;
    if (Math.abs(pct) < 0.5) { el.textContent = 'estável vs período anterior'; el.className = 'kcard-delta neutral'; return; }
    const good = invert ? pct < 0 : pct > 0;
    el.textContent = (pct > 0 ? '↑ ' : '↓ ') + Math.abs(pct).toFixed(0) + '% vs período anterior';
    el.className = 'kcard-delta ' + (good ? 'up' : 'down');
  }

  let chMetaDaily = null, chMetaMix = null, chCompare = null;

  function applyRange(from, to, label) {
    const cur = sumRange(from, to);
    const days = Math.round((new Date(to) - new Date(from)) / 86400000) + 1;
    const pTo = new Date(new Date(from) - 86400000);
    const pFrom = new Date(pTo - (days - 1) * 86400000);
    const prev = sumRange(dstr(pFrom), dstr(pTo));

    setText('mSpend', fmtBRL(cur.s));            setDelta('mSpend', cur.s, prev.s, false);
    setText('mResults', fmtNum(cur.r));          setDelta('mResults', cur.r, prev.r, false);
    const cpl = cur.r ? cur.s / cur.r : 0, pcpl = prev.r ? prev.s / prev.r : 0;
    setText('mCpl', fmtBRL(cpl));                setDelta('mCpl', cpl, pcpl, true);
    if (HAS_ROAS) {
      setText('mRev', fmtBRL(cur.v));            setDelta('mRev', cur.v, prev.v, false);
      const roas = cur.s ? cur.v / cur.s : 0, proas = prev.s ? prev.v / prev.s : 0;
      setText('mRoas', fmtX(roas));              setDelta('mRoas', roas, proas, false);
    } else {
      setText('mMsgs', fmtNum(cur.m));           setDelta('mMsgs', cur.m, prev.m, false);
      const cm = cur.m ? cur.s / cur.m : 0, pcm = prev.m ? prev.s / prev.m : 0;
      setText('mCostMsg', fmtBRL(cm));           setDelta('mCostMsg', cm, pcm, true);
    }
    setText('mImp', fmtNum(cur.i));              setDelta('mImp', cur.i, prev.i, false);
    const cpm = cur.i ? cur.s / cur.i * 1000 : 0, pcpm = prev.i ? prev.s / prev.i * 1000 : 0;
    setText('mCpm', fmtBRL(cpm));                setDelta('mCpm', cpm, pcpm, true);
    setText('mClicks', fmtNum(cur.c));           setDelta('mClicks', cur.c, prev.c, false);
    const ctr = cur.i ? cur.c / cur.i * 100 : 0, pctr = prev.i ? prev.c / prev.i * 100 : 0;
    setText('mCtr', fmtPct(ctr));                setDelta('mCtr', ctr, pctr, false);
    const cpc = cur.c ? cur.s / cur.c : 0, pcpc = prev.c ? prev.s / prev.c : 0;
    setText('mCpc', fmtBRL(cpc));                setDelta('mCpc', cpc, pcpc, true);
    setText('periodTag', '· ' + label);

    // Gráfico de evolução
    const rows = DM.filter(x => x.d >= from && x.d <= to);
    const labels = rows.map(x => x.d.slice(8) + '/' + x.d.slice(5, 7));
    if (chMetaDaily) {
      chMetaDaily.data.labels = labels;
      chMetaDaily.data.datasets[0].data = rows.map(x => x.s);
      chMetaDaily.data.datasets[1].data = rows.map(x => x.r);
      chMetaDaily.update();
    }
    if (chMetaMix) {
      chMetaMix.data.datasets[0].data = [cur.r, Math.max(0, cur.c - cur.r)];
      chMetaMix.update();
    }
    // Comparativo padrão: atual vs anterior
    updateCompare(cur, prev, label, 'período anterior equivalente');
  }

  function updateCompare(a, b, labelA, labelB) {
    if (!chCompare) return;
    chCompare.data.datasets[0].data = [Math.round(a.s * 100) / 100, a.r];
    chCompare.data.datasets[1].data = [Math.round(b.s * 100) / 100, b.r];
    chCompare.update();
    const cplA = a.r ? a.s / a.r : 0, cplB = b.r ? b.s / b.r : 0;
    const diff = b.r ? ((a.r - b.r) / b.r * 100).toFixed(0) : '—';
    document.getElementById('cmpSummary').innerHTML =
      '<b style="color:var(--gold)">' + labelA + ':</b> ' + fmtBRL(a.s) + ' · ' + fmtNum(a.r) + ' ' + RESULT_LABEL.toLowerCase() +
      ' (custo ' + fmtBRL(cplA) + ') &nbsp;•&nbsp; <b style="color:#888">' + labelB + ':</b> ' + fmtBRL(b.s) + ' · ' +
      fmtNum(b.r) + ' (custo ' + fmtBRL(cplB) + ') &nbsp;•&nbsp; variação de resultados: <b>' + diff + '%</b>';
  }

  function applyCompare() {
    const af = document.getElementById('cmpAFrom').value, at = document.getElementById('cmpATo').value;
    const bf = document.getElementById('cmpBFrom').value, bt = document.getElementById('cmpBTo').value;
    if (!(af && at && bf && bt)) return;
    updateCompare(sumRange(af, at), sumRange(bf, bt),
                  'Período A (' + af.slice(8) + '/' + af.slice(5,7) + '–' + at.slice(8) + '/' + at.slice(5,7) + ')',
                  'Período B (' + bf.slice(8) + '/' + bf.slice(5,7) + '–' + bt.slice(8) + '/' + bt.slice(5,7) + ')');
  }

  function setPeriod(btn, key) {
    document.querySelectorAll('.pbtn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('customWrap').classList.remove('show');
    const today = new Date();
    let from, to = dstr(today), label;
    if (key === '1d')      { from = to; label = 'hoje'; }
    else if (key === '7d') { from = dstr(new Date(today - 6 * 86400000)); label = 'últimos 7 dias'; }
    else if (key === '30d'){ from = dstr(new Date(today - 29 * 86400000)); label = 'últimos 30 dias'; }
    else if (key === '90d'){ from = dstr(new Date(today - 89 * 86400000)); label = 'últimos 3 meses'; }
    else if (key === '180d'){ from = dstr(new Date(today - 179 * 86400000)); label = 'últimos 6 meses'; }
    else if (key === 'month') { from = to.slice(0, 8) + '01'; label = 'mês atual'; }
    else if (key === 'lmonth') {
      const d = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      from = dstr(d);
      to = dstr(new Date(today.getFullYear(), today.getMonth(), 0));
      label = 'mês passado';
    }
    applyRange(from, to, label);
  }

  function toggleCustom(btn) {
    document.querySelectorAll('.pbtn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('customWrap').classList.toggle('show');
  }

  function applyCustom() {
    const f = document.getElementById('dateFrom').value, t = document.getElementById('dateTo').value;
    if (f && t) applyRange(f, t, f.slice(8) + '/' + f.slice(5,7) + ' a ' + t.slice(8) + '/' + t.slice(5,7));
  }

  // ── Inicialização dos gráficos Meta ──
  chMetaDaily = new Chart(document.getElementById('chartMetaDaily'), { type: 'line',
    data: { labels: [], datasets: [
      { label: 'Investimento', data: [], borderColor: '#F5A623', backgroundColor: 'rgba(245,166,35,.07)', tension: .4, fill: true, pointRadius: 2, yAxisID: 'y' },
      { label: RESULT_LABEL, data: [], borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,.07)', tension: .4, fill: true, pointRadius: 2, yAxisID: 'y1' }]},
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: false } },
      scales: { x: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#555', font: { size: 10 }, maxTicksLimit: 15 } },
        y: { position: 'left', grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#F5A623', font: { size: 10 }, callback: v => 'R$' + v } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#22c55e', font: { size: 10 } } } } } });

  chMetaMix = new Chart(document.getElementById('chartMetaMix'), { type: 'doughnut',
    data: { labels: [RESULT_LABEL, 'Cliques s/ conversão'],
      datasets: [{ data: [0, 0], backgroundColor: ['#22c55e', '#2a2a2a'], borderWidth: 0, hoverOffset: 6 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: { legend: { position: 'bottom', labels: { color: '#666', font: { size: 10 }, padding: 12, boxWidth: 8, boxHeight: 8 } } } } });

  chCompare = new Chart(document.getElementById('chartCompare'), { type: 'bar',
    data: { labels: ['Investimento (R$)', RESULT_LABEL],
      datasets: [
        { label: 'A', data: [0, 0], backgroundColor: '#F5A623', borderRadius: 6, barPercentage: .6 },
        { label: 'B', data: [0, 0], backgroundColor: '#444', borderRadius: 6, barPercentage: .6 }]},
    options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: { x: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#666', font: { size: 10 } } },
        y: { grid: { display: false }, ticks: { color: '#888', font: { size: 11, weight: '600' } } } } } });

  // Estado inicial: últimos 30 dias
  const _t = new Date();
  applyRange(dstr(new Date(_t - 29 * 86400000)), dstr(_t), 'últimos 30 dias');
"""

    if has_goog:
        gdc = g.get("daily_compact", [])
        gm = g["metrics"]
        gcamp_labels = [cc["name"][:28] for cc in g["campaigns"][:6]]
        gcamp_spend  = [round(cc["spend"], 2) for cc in g["campaigns"][:6]]
        gdias = [d["d"][8:] + "/" + d["d"][5:7] for d in gdc[-30:]]
        ginv  = [d["s"] for d in gdc[-30:]]
        gconv = [d["cv"] for d in gdc[-30:]]
        js += f"""
  new Chart(document.getElementById('chartGoogleDaily'),{{type:'line',data:{{labels:{json.dumps(gdias)},datasets:[
    {{label:'Investimento',data:{json.dumps(ginv)},borderColor:'#F5A623',backgroundColor:'rgba(245,166,35,.07)',tension:.4,fill:true,pointRadius:2,yAxisID:'y'}},
    {{label:'Conversões',data:{json.dumps(gconv)},borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.07)',tension:.4,fill:true,pointRadius:2,yAxisID:'y1'}}]}},
    options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:false}}}},
    scales:{{x:{{grid:{{color:'rgba(255,255,255,.04)'}},ticks:{{color:'#555',font:{{size:10}}}}}},
    y:{{position:'left',grid:{{color:'rgba(255,255,255,.04)'}},ticks:{{color:'#F5A623',font:{{size:10}},callback:v=>'R$'+v}}}},
    y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{color:'#22c55e',font:{{size:10}}}}}}}}}}}});
  new Chart(document.getElementById('chartGoogleCampDonut'),{{type:'doughnut',data:{{
    labels:{json.dumps(gcamp_labels, ensure_ascii=False)},
    datasets:[{{data:{json.dumps(gcamp_spend)},backgroundColor:['#22c55e','#F5A623','#3b82f6','#a855f7','#ef4444','#06b6d4'],borderWidth:0,hoverOffset:6}}]}},
    options:{{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{{legend:{{position:'bottom',labels:{{color:'#888',font:{{size:10}},padding:10,boxWidth:8,boxHeight:8}}}}}}}}}});"""

    if dual:
        meta_by_day = {d["d"]: d["s"] for d in meta.get("daily_compact", [])[-30:]}
        goog_by_day = {d["d"]: d["s"] for d in g.get("daily_compact", [])[-30:]}
        all_days = sorted(set(list(meta_by_day.keys()) + list(goog_by_day.keys())))
        cdias = [d[8:] + "/" + d[5:7] for d in all_days]
        cmeta = [round(meta_by_day.get(d, 0), 2) for d in all_days]
        cgoog = [round(goog_by_day.get(d, 0), 2) for d in all_days]
        mm, gm = meta["metrics"], g["metrics"]
        js += f"""
  new Chart(document.getElementById('chartConsolidadoDaily'),{{type:'bar',data:{{labels:{json.dumps(cdias)},datasets:[
    {{label:'Meta Ads',data:{json.dumps(cmeta)},backgroundColor:'#3b82f6',stack:'s'}},
    {{label:'Google Ads',data:{json.dumps(cgoog)},backgroundColor:'#22c55e',stack:'s'}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#888',font:{{size:10}},boxWidth:10,boxHeight:10}}}}}},
    scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{color:'#555',font:{{size:9}}}}}},
    y:{{stacked:true,grid:{{color:'rgba(255,255,255,.04)'}},ticks:{{color:'#666',font:{{size:10}},callback:v=>'R$'+v}}}}}}}}}});
  new Chart(document.getElementById('chartSplit'),{{type:'doughnut',data:{{
    labels:['Meta Ads','Google Ads'],
    datasets:[{{data:[{round(mm["spend"],2)},{round(gm["spend"],2)}],backgroundColor:['#3b82f6','#22c55e'],borderWidth:0,hoverOffset:6}}]}},
    options:{{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{{legend:{{position:'bottom',labels:{{color:'#888',font:{{size:11}},padding:14,boxWidth:10,boxHeight:10}}}}}}}}}});"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — {name} · A2 Digital</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="nav-left">
    {f'<img src="{logo}" class="nav-logo" alt="A2 Digital">' if logo else '<span style="color:var(--gold);font-weight:800">A2</span>'}
    <div class="nav-divider"></div>
    <span class="nav-client">{name}</span>
  </div>
  <div class="nav-tabs">{tab_btns}</div>
  <div class="nav-right">
    <div class="updated-pill"><div class="updated-dot"></div>Atualizado {now}</div>
  </div>
</nav>
{pages}
<script>
function switchCampPeriod(btn, p) {{
  document.querySelectorAll('#page-campanhas .pbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('campBlocks30').style.display = p === '30d' ? '' : 'none';
  document.getElementById('campBlocks90').style.display = p === '90d' ? '' : 'none';
}}
function switchCreatPeriod(btn, p) {{
  document.querySelectorAll('#page-criativos .pbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('creatTable30').style.display = p === '30d' ? '' : 'none';
  document.getElementById('creatTable90').style.display = p === '90d' ? '' : 'none';
}}
function showPage(id,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(btn) btn.classList.add('active');
}}
Chart.defaults.color='#666';Chart.defaults.borderColor='#222';Chart.defaults.font.family='Inter';
{js}
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    print(f"Gerando dashboards para {len(ACCOUNTS)} contas...")
    ok, fail = 0, 0

    # Garantir CNAME para domínio customizado
    cname_path = OUT_DIR / "CNAME"
    if not cname_path.exists():
        with open(cname_path, "w") as f:
            f.write("dashboard.a2digitalmkt.com.br")
        print("  ✓ CNAME gerado")

    for account in ACCOUNTS:
        platforms = account.get("platforms", ["meta"])
        slug = account["slug"]
        print(f"  → {account['name']} ({', '.join(platforms)})")

        meta_data = goog_data = None

        if "meta" in platforms:
            try:
                meta_data = fetch_meta(account)
            except Exception as e:
                print(f"     ✗ Meta ERRO: {e}", file=sys.stderr)

        if "google" in platforms:
            try:
                goog_data = fetch_google(account)
            except Exception as e:
                print(f"     ✗ Google ERRO: {e}", file=sys.stderr)

        if not meta_data and not goog_data:
            print(f"     ✗ Sem dados — pulando")
            fail += 1
            continue

        try:
            html = render(account, meta_data, goog_data)
            with open(OUT_DIR / f"{slug}.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"     ✓ docs/{slug}.html")
            ok += 1
        except Exception as e:
            print(f"     ✗ Render ERRO: {e}", file=sys.stderr)
            fail += 1

    print(f"Concluído: {ok} ok, {fail} falhas.")


if __name__ == "__main__":
    main()
