"""
relatorio_semanal_metas.py

Relatório semanal (segunda, quarta e sexta) enviado ao Telegram, contendo
o pacing de meta mensal por conta (bloco_meta_semanal), incluindo o ROAS
do mês — a bonificação exige meta de faturamento batida E ROAS >= 5.

Agora enviado para o grupo "Congressos - relatórios de metas", não mais
no direct do Telegram.

Variáveis de ambiente esperadas (GitHub Actions secrets):
- META_ACCESS_TOKEN
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID_GRUPO_CONGRESSOS
"""

import os
from datetime import date, timedelta
import requests

from metas_pacing import METAS, bloco_meta_semanal

META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID_GRUPO_CONGRESSOS"]

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


def dados_acumulados_mes(account_id: str) -> tuple[float, float]:
    """Busca receita (purchase value) e ROAS acumulados do dia 1 até ontem via Graph API.

    Retorna (receita_acumulada, roas_mes). ROAS = receita / gasto no período.
    """
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    primeiro_dia = hoje.replace(day=1)

    # Se hoje é dia 1, o mês ainda não teve nenhum dia fechado.
    if ontem.month != hoje.month:
        return 0.0, 0.0

    params = {
        "access_token": META_ACCESS_TOKEN,
        "level": "account",
        "fields": "action_values,spend",
        "time_range": f'{{"since":"{primeiro_dia.isoformat()}","until":"{ontem.isoformat()}"}}',
    }
    resp = requests.get(f"{GRAPH_URL}/act_{account_id}/insights", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return 0.0, 0.0

    receita = 0.0
    action_values = data[0].get("action_values", [])
    for item in action_values:
        if item.get("action_type") == "omni_purchase":
            receita = float(item.get("value", 0))
            break

    gasto = float(data[0].get("spend", 0))
    roas = receita / gasto if gasto > 0 else 0.0

    return receita, roas


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

        receita, roas = dados_acumulados_mes(account_id)
        bloco = bloco_meta_semanal(account_id, receita, roas)
        if not bloco:
            continue

        nome = NOMES_CONTAS.get(account_id, account_id)
        msg = f"*{nome}*\n{bloco}"
        enviar_telegram(msg)


if __name__ == "__main__":
    main()
