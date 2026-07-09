"""
relatorio_semanal_metas.py

Relatório semanal (segunda, quarta e sexta) enviado ao Telegram, contendo
apenas o pacing de meta mensal por conta (bloco_meta_semanal).
Substitui integralmente o antigo roas_report.py / daily_report.yml, que não
roda mais.

Variáveis de ambiente esperadas (GitHub Actions secrets):
- META_ACCESS_TOKEN
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
from datetime import date, timedelta
import requests

from metas_pacing import METAS, bloco_meta_semanal

META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

GRAPH_URL = "https://graph.facebook.com/v20.0"

# Nome de exibição de cada conta (mesma chave usada em METAS, sem "act_")
NOMES_CONTAS = {
    "1123910629201094": "16CIF",
    "928960755916597": "Interpilates",
    "565062448809883": "CONIFIC",
    "1679280069737129": "CARDIO",
    "700954712494713": "CBFD",
    "2352951311846960": "CONSULFISIO",
    "1378989810350371": "INTERFITO",
    "892752402026712": "CONFIDEFE 11",
}


def receita_acumulada_mes(account_id: str) -> float:
    """Busca a receita (valor de compras) acumulada do dia 1 até ontem via Graph API."""
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    primeiro_dia = hoje.replace(day=1)

    # Se hoje é dia 1, o mês ainda não teve nenhum dia fechado.
    if ontem.month != hoje.month:
        return 0.0

    params = {
        "access_token": META_ACCESS_TOKEN,
        "level": "account",
        "fields": "action_values",
        "time_range": f'{{"since":"{primeiro_dia.isoformat()}","until":"{ontem.isoformat()}"}}',
    }
    resp = requests.get(f"{GRAPH_URL}/act_{account_id}/insights", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return 0.0

    action_values = data[0].get("action_values", [])
    for item in action_values:
        if item.get("action_type") == "omni_purchase":
            return float(item.get("value", 0))
    return 0.0


def enviar_telegram(texto: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto}, timeout=30)
    resp.raise_for_status()


def main() -> None:
    hoje = date.today()
    header = f"📊 Pacing de metas — {hoje.strftime('%d/%m/%Y')}"
    enviar_telegram(header)

    for account_id in METAS:
        if hoje.month not in METAS[account_id]:
            continue

        receita = receita_acumulada_mes(account_id)
        bloco = bloco_meta_semanal(account_id, receita)
        if not bloco:
            continue

        nome = NOMES_CONTAS.get(account_id, account_id)
        msg = f"*{nome}*\n{bloco}"
        enviar_telegram(msg)


if __name__ == "__main__":
    main()
