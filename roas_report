import os
import requests
from datetime import datetime, timedelta
import time

# ──────────────────────────────────────────────
# CONFIGURAÇÕES
# ──────────────────────────────────────────────
META_ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
AD_ACCOUNT_IDS = [x.strip() for x in os.environ["META_AD_ACCOUNT_IDS"].split(",")]

# Datas
TODAY = datetime.now()
D1 = TODAY - timedelta(days=1)
D1_STR = D1.strftime("%Y-%m-%d")
D4_STR = (TODAY - timedelta(days=4)).strftime("%Y-%m-%d")  # para janela de 3 dias antes de D-1
D8_STR = (TODAY - timedelta(days=8)).strftime("%Y-%m-%d")  # para janela de 7 dias antes de D-1
MES_INICIO = D1.replace(day=1).strftime("%Y-%m-%d")
MESES = {"January": "Janeiro", "February": "Fevereiro", "March": "Março", "April": "Abril", "May": "Maio", "June": "Junho", "July": "Julho", "August": "Agosto", "September": "Setembro", "October": "Outubro", "November": "Novembro", "December": "Dezembro"}
MES_NOME = MESES[D1.strftime("%B")] + D1.strftime("/%Y")


# ──────────────────────────────────────────────
# HELPER — buscar insights de uma conta num período
# ──────────────────────────────────────────────
def get_insights(account_id, date_start, date_end):
    url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
    params = {
        "access_token": META_ACCESS_TOKEN,
        "fields": "spend,purchase_roas,actions,action_values",
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "level": "account",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json().get("data", [])
    return data[0] if data else {}


def parse_insights(data):
    spend = float(data.get("spend", 0) or 0)
    roas_list = data.get("purchase_roas", [])
    roas = float(roas_list[0]["value"]) if roas_list else 0.0
    revenue = spend * roas

    # Vendas (purchases)
    vendas = 0
    actions = data.get("actions", [])
    for action in actions:
        if action.get("action_type") == "purchase":
            vendas = int(float(action.get("value", 0)))
            break

    # Funil
    initiate_checkout = 0
    page_view = 0
    for action in actions:
        if action.get("action_type") == "initiate_checkout":
            initiate_checkout = int(float(action.get("value", 0)))
        if action.get("action_type") == "view_content":
            page_view = int(float(action.get("value", 0)))

    checkout_rate = (initiate_checkout / page_view * 100) if page_view > 0 else 0
    purchase_rate = (vendas / initiate_checkout * 100) if initiate_checkout > 0 else 0

    return {
        "spend": spend,
        "roas": roas,
        "revenue": revenue,
        "vendas": vendas,
        "checkout_rate": checkout_rate,
        "purchase_rate": purchase_rate,
    }


def evolucao(roas_atual, roas_anterior):
    if roas_anterior == 0 and roas_atual == 0:
        return "N/D"
    if roas_anterior == 0:
        return "+∞%"
    pct = ((roas_atual - roas_anterior) / roas_anterior) * 100
    sinal = "+" if pct >= 0 else ""
    return f"{sinal}{pct:.2f}%"


# ──────────────────────────────────────────────
# BUSCAR NOME DA CONTA
# ──────────────────────────────────────────────
def get_account_name(account_id):
    url = f"https://graph.facebook.com/v19.0/{account_id}"
    params = {"access_token": META_ACCESS_TOKEN, "fields": "name"}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("name", account_id)


# ──────────────────────────────────────────────
# MONTAR BLOCO DE CADA CONTA
# ──────────────────────────────────────────────
def build_account_block(account_id):
    name = get_account_name(account_id)

    # D-1
    d1_data = parse_insights(get_insights(account_id, D1_STR, D1_STR))

    # 3 dias antes de D-1 (D-4 até D-2)
    d2_str = (TODAY - timedelta(days=2)).strftime("%Y-%m-%d")
    prev3_data = parse_insights(get_insights(account_id, D4_STR, d2_str))

    # 7 dias antes de D-1 (D-8 até D-2)
    prev7_data = parse_insights(get_insights(account_id, D8_STR, d2_str))

    # Acumulado do mês até D-1
    mes_data = parse_insights(get_insights(account_id, MES_INICIO, D1_STR))

    # Evoluções (ROAS D-1 vs períodos anteriores)
    evo3 = evolucao(d1_data["roas"], prev3_data["roas"])
    evo7 = evolucao(d1_data["roas"], prev7_data["roas"])

    # Evoluções acumulado (ROAS mês vs períodos anteriores)
    evo3_mes = evolucao(mes_data["roas"], prev3_data["roas"])
    evo7_mes = evolucao(mes_data["roas"], prev7_data["roas"])

    lines = [
        f"{'─'*30}",
        f"🏢 {name}",
        f"",
        f"📅 D-1 ({D1_STR})",
        f"Investimento: R$ {d1_data['spend']:,.2f}",
        f"Vendas: {d1_data['vendas']}",
        f"Valor de Venda: R$ {d1_data['revenue']:,.2f}",
        f"ROAS: {d1_data['roas']:.2f}",
        f"Evolução ROAS 3 dias: {evo3}",
        f"Evolução ROAS 7 dias: {evo7}",
        f"",
        f"📆 Acumulado Mês (até D-1)",
        f"Investimento: R$ {mes_data['spend']:,.2f}",
        f"Vendas: {mes_data['vendas']}",
        f"Valor de Venda: R$ {mes_data['revenue']:,.2f}",
        f"ROAS: {mes_data['roas']:.2f}",
        f"Evolução ROAS 3 dias: {evo3_mes}",
        f"Evolução ROAS 7 dias: {evo7_mes}",
        f"",
        f"🔻 Funil de Conversão:",
        f"InitiateCheckout / PageView: {mes_data['checkout_rate']:.2f}%",
        f"Compra / InitiateCheckout: {mes_data['purchase_rate']:.2f}%",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# ENVIAR PARA O TELEGRAM
# ──────────────────────────────────────────────
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, json=payload)
    response.raise_for_status()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("Buscando dados das contas...")

    # Cabeçalho
    cabecalho = (
        f"📊 RELATORIO DIARIO DE ROAS — CONGRESSOS\n"
        f"D-1: {D1_STR} | Acumulado: {MES_NOME}"
    )
    send_telegram(cabecalho)
    print("Cabecalho enviado.")

    # Uma mensagem por conta
    for i, account_id in enumerate(AD_ACCOUNT_IDS):
        print(f"Processando conta {i+1}/{len(AD_ACCOUNT_IDS)}: {account_id}")
        try:
            block = build_account_block(account_id)
            send_telegram(block)
            time.sleep(1)  # evitar rate limit do Telegram
        except Exception as e:
            send_telegram(f"Erro ao processar conta {account_id}:\n{str(e)}")

    print("Relatorio enviado com sucesso!")
