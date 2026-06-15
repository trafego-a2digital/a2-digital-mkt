"""
comum.py — Funções compartilhadas entre as automações de Meta Ads.
Autor: Wesley Franco (W Digital / A2 Digital Marketing)

Requer variáveis de ambiente (GitHub Secrets):
  META_ACCESS_TOKEN   — token de usuário do sistema (longa duração)
  TELEGRAM_BOT_TOKEN  — token do bot
  TELEGRAM_CHAT_ID    — chat ID de destino
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone

API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# Fuso de Brasília (sem dependência externa)
TZ_BR = timezone(timedelta(hours=-3))

# Tipos de ação que contam como "resultado" (mesma lógica do Relatório A2)
ACTION_TYPES_RESULTADO = [
    "onsite_conversion.messaging_conversation_started_7d",
    "offsite_conversion.fb_pixel_lead",
    "lead",
]


def carregar_config():
    caminho = os.path.join(os.path.dirname(__file__), "..", "config", "contas.json")
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def hoje_br():
    return datetime.now(TZ_BR).date()


# ---------------------------------------------------------------- Meta API --

def _get(url, params, tentativas=3):
    """GET com retry simples para rate limit / erros transitórios."""
    params = dict(params or {})
    params["access_token"] = META_TOKEN
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            corpo = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            codigo = (corpo.get("error") or {}).get("code")
            # 17 / 4 / 32 = rate limit → espera e tenta de novo
            if codigo in (4, 17, 32, 613) and i < tentativas - 1:
                time.sleep(30 * (i + 1))
                continue
            return {"erro": corpo.get("error", {"message": r.text[:300]})}
        except requests.RequestException as e:
            if i < tentativas - 1:
                time.sleep(10)
                continue
            return {"erro": {"message": str(e)}}
    return {"erro": {"message": "Falha após retries"}}


def paginar(url, params):
    """Itera todas as páginas de um endpoint da Graph API."""
    dados = []
    resp = _get(url, params)
    while True:
        if "erro" in resp:
            return dados, resp["erro"]
        dados.extend(resp.get("data", []))
        prox = (resp.get("paging") or {}).get("next")
        if not prox:
            return dados, None
        resp = _get(prox, {})


def insights_conta(account_id, since, until, level="campaign", fields=None,
                   filtros=None, time_increment=None):
    """
    Busca insights de uma conta entre duas datas (date objects ou 'YYYY-MM-DD').
    level: account | campaign | adset | ad
    """
    fields = fields or [
        "campaign_id", "campaign_name", "objective",
        "spend", "impressions", "clicks", "ctr", "frequency", "actions",
    ]
    params = {
        "level": level,
        "fields": ",".join(fields),
        "time_range": json.dumps({"since": str(since), "until": str(until)}),
        "limit": 200,
    }
    if filtros:
        params["filtering"] = json.dumps(filtros)
    if time_increment:
        params["time_increment"] = time_increment
    return paginar(f"{BASE_URL}/act_{account_id}/insights", params)


def extrair_resultados(linha):
    """Soma as ações que contam como resultado (msgs iniciadas + leads)."""
    total = 0
    for acao in linha.get("actions", []) or []:
        if acao.get("action_type") in ACTION_TYPES_RESULTADO:
            try:
                total += int(float(acao.get("value", 0)))
            except (TypeError, ValueError):
                pass
    return total


def metricas_periodo(account_id, since, until, level="campaign"):
    """
    Retorna lista de dicts normalizados:
    {nome, id, objetivo, gasto, impressoes, cliques, ctr, freq, resultados, cpr}
    """
    linhas, erro = insights_conta(account_id, since, until, level=level)
    if erro:
        return [], erro
    saida = []
    for ln in linhas:
        gasto = float(ln.get("spend", 0) or 0)
        if gasto <= 0:
            continue
        res = extrair_resultados(ln)
        saida.append({
            "nome": ln.get("campaign_name") or ln.get("ad_name") or "?",
            "id": ln.get("campaign_id") or ln.get("ad_id"),
            "objetivo": ln.get("objective", ""),
            "gasto": gasto,
            "impressoes": int(ln.get("impressions", 0) or 0),
            "cliques": int(ln.get("clicks", 0) or 0),
            "ctr": float(ln.get("ctr", 0) or 0),
            "freq": float(ln.get("frequency", 0) or 0),
            "resultados": res,
            "cpr": round(gasto / res, 2) if res > 0 else None,
        })
    return saida, None


def status_conta(account_id):
    """account_status: 1=ativa, 2=desativada, 3=não confirmada, 101=fechada..."""
    resp = _get(f"{BASE_URL}/act_{account_id}", {
        "fields": "name,account_status,disable_reason,amount_spent,currency"
    })
    return resp


def detalhes_anuncio(ad_id):
    """Link de prévia compartilhável + data de criação do anúncio."""
    return _get(f"{BASE_URL}/{ad_id}", {
        "fields": "preview_shareable_link,created_time"
    })


def anuncios_com_problema(account_id):
    """Anúncios reprovados ou com erro de entrega (campanhas ativas)."""
    campos = "name,effective_status,ad_review_feedback,campaign{name}"
    params = {
        "fields": campos,
        "filtering": json.dumps([{
            "field": "effective_status",
            "operator": "IN",
            "value": ["DISAPPROVED", "WITH_ISSUES", "PENDING_REVIEW"],
        }]),
        "limit": 100,
    }
    return paginar(f"{BASE_URL}/act_{account_id}/ads", params)


# --------------------------------------------------------------- Telegram --

def enviar_telegram(texto, parse_mode="HTML"):
    """Envia mensagem ao Telegram, dividindo se passar de 4096 chars."""
    if not TG_TOKEN or not TG_CHAT:
        print("[AVISO] Telegram não configurado. Mensagem:\n", texto)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    partes = []
    while texto:
        if len(texto) <= 4000:
            partes.append(texto)
            break
        corte = texto.rfind("\n", 0, 4000)
        corte = corte if corte > 0 else 4000
        partes.append(texto[:corte])
        texto = texto[corte:]
    for p in partes:
        r = requests.post(url, json={
            "chat_id": TG_CHAT, "text": p,
            "parse_mode": parse_mode, "disable_web_page_preview": True,
        }, timeout=30)
        if r.status_code != 200:
            print("[ERRO Telegram]", r.text[:300])


def enviar_documento_telegram(caminho, legenda=""):
    """Envia um arquivo (ex.: JSON do relatório) ao Telegram."""
    if not TG_TOKEN or not TG_CHAT:
        print("[AVISO] Telegram não configurado. Arquivo:", caminho)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
    with open(caminho, "rb") as f:
        r = requests.post(url, data={"chat_id": TG_CHAT, "caption": legenda},
                          files={"document": f}, timeout=60)
    if r.status_code != 200:
        print("[ERRO Telegram doc]", r.text[:300])


def fmt_brl(v):
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
