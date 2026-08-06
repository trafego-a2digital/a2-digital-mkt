"""
relatorio_funil_diario.py

Relatório diário de métricas de funil (D-1) para as contas de congresso.
Métricas, na ordem em que acontecem no funil:
  CTR -> Taxa de Conexão -> CPC -> Taxa de Add to Cart -> Taxa de Checkout
  -> Taxa de Finalização de Compra -> CPA

Enviado via Telegram, um bloco por conta, no grupo dedicado
"Congressos - relatório de funil".

Variáveis de ambiente esperadas (GitHub Actions secrets):
- META_ACCESS_TOKEN
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID_GRUPO_FUNIL
"""

import os
from datetime import date, timedelta
import requests

META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID_GRUPO_FUNIL = os.environ["TELEGRAM_CHAT_ID_GRUPO_FUNIL"]

GRAPH_URL = "https://graph.facebook.com/v20.0"

# Nome de exibição de cada conta (mesmas 8 contas do relatório de metas)
CONTAS = {
    "1123910629201094": "16CIF",
    "928960755916597": "Interpilates",
    "565062448809883": "CONIFIC",
    "1679280069737129": "CARDIO",
    "700954712494713": "CBFD",
    "2352951311846960": "CONSULFISIO",
    "1378989810350371": "INTERFITO",
    "892752402026712": "CONFIDEFE 11",
}

EMOJI_CONTA = "🏥"


def _extrai_action(actions: list, action_type: str) -> float:
    """Busca o valor de um action_type específico dentro da lista `actions` do Graph API."""
    if not actions:
        return 0.0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0


def busca_metricas_funil_d1(account_id: str) -> dict:
    """Busca as métricas de funil de D-1 (dia anterior) para uma conta via Graph API."""
    ontem = date.today() - timedelta(days=1)
    data_str = ontem.strftime("%Y-%m-%d")

    params = {
        "access_token": META_ACCESS_TOKEN,
        "fields": "spend,impressions,actions",
        "time_range": f'{{"since":"{data_str}","until":"{data_str}"}}',
        "level": "account",
    }
    resp = requests.get(f"{GRAPH_URL}/act_{account_id}/insights", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    if not data:
        return {
            "data_ref": data_str,
            "spend": 0.0,
            "impressions": 0,
            "link_clicks": 0,
            "pageviews": 0,
            "add_to_cart": 0,
            "initiate_checkout": 0,
            "purchases": 0,
            "sem_dados": True,
        }

    row = data[0]
    actions = row.get("actions", [])

    return {
        "data_ref": data_str,
        "spend": float(row.get("spend", 0)),
        "impressions": int(row.get("impressions", 0)),
        "link_clicks": _extrai_action(actions, "link_click"),
        "pageviews": _extrai_action(actions, "landing_page_view"),
        "add_to_cart": _extrai_action(actions, "omni_add_to_cart"),
        "initiate_checkout": _extrai_action(actions, "omni_initiated_checkout"),
        "purchases": _extrai_action(actions, "omni_purchase"),
        "sem_dados": False,
    }


def _pct(numerador: float, denominador: float) -> str:
    if denominador <= 0:
        return "—"
    return f"{(numerador / denominador) * 100:.1f}%".replace(".", ",")


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def monta_bloco_conta(nome: str, m: dict) -> str:
    if m["sem_dados"]:
        return f"{EMOJI_CONTA} {nome}\nSem dados para o dia."

    ctr = _pct(m["link_clicks"], m["impressions"])
    taxa_conexao = _pct(m["pageviews"], m["link_clicks"])
    cpc = _moeda(m["spend"] / m["link_clicks"]) if m["link_clicks"] > 0 else "—"
    taxa_add_to_cart = _pct(m["add_to_cart"], m["pageviews"])
    taxa_checkout = _pct(m["initiate_checkout"], m["pageviews"])
    taxa_finalizacao = _pct(m["purchases"], m["initiate_checkout"])
    cpa = _moeda(m["spend"] / m["purchases"]) if m["purchases"] > 0 else "—"

    return (
        f"{EMOJI_CONTA} {nome}\n"
        f"CTR: {ctr}\n"
        f"Taxa de Conexão: {taxa_conexao}\n"
        f"CPC: {cpc}\n"
        f"Taxa de Add to Cart: {taxa_add_to_cart}\n"
        f"Taxa de Checkout: {taxa_checkout}\n"
        f"Taxa de Finalização de Compra: {taxa_finalizacao}\n"
        f"CPA: {cpa}"
    )


def monta_mensagem() -> str:
    ontem = date.today() - timedelta(days=1)
    data_fmt = ontem.strftime("%d/%m/%Y")

    linhas = [
        "📊 RELATÓRIO DE FUNIL — CONGRESSOS",
        f"📅 Referente a: {data_fmt} (D-1)",
        "",
    ]

    for account_id, nome in CONTAS.items():
        linhas.append("━━━━━━━━━━━━━━━━━━━━")
        linhas.append("")
        try:
            metricas = busca_metricas_funil_d1(account_id)
            linhas.append(monta_bloco_conta(nome, metricas))
        except Exception as e:
            linhas.append(f"{EMOJI_CONTA} {nome}\n⚠️ Erro ao buscar dados: {e}")
        linhas.append("")

    return "\n".join(linhas)


def envia_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID_GRUPO_FUNIL, "text": mensagem},
        timeout=30,
    )
    resp.raise_for_status()


def main():
    mensagem = monta_mensagem()
    envia_telegram(mensagem)
    print("Relatório de funil enviado com sucesso.")


if __name__ == "__main__":
    main()
