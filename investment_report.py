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

TODAY = datetime.now()
DIAS_NO_MES = (TODAY.replace(month=TODAY.month % 12 + 1, day=1) - timedelta(days=1)).day
DIAS_PASSADOS = TODAY.day - 1
DIAS_RESTANTES = DIAS_NO_MES - DIAS_PASSADOS
NA_SEGUNDA_METADE = TODAY.day > (DIAS_NO_MES / 2)
ALERTA_RECARGA_ATIVO = 3 <= DIAS_RESTANTES <= 5

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
MES_NOME = f"{MESES_PT[TODAY.month]}/{TODAY.year}"

SEMANA_FIM = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")
SEMANA_INICIO = (TODAY - timedelta(days=7)).strftime("%Y-%m-%d")
MES_INICIO_STR = TODAY.replace(day=1).strftime("%Y-%m-%d")
MES_FIM_STR = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")

CONTAS = [
    {"id": "act_208064071916203",  "nome": "Clay",                "orcamento": 7900.00},
    {"id": "act_2130371487349249", "nome": "Dr. Tiago Alcântara", "orcamento": 2600.00},
    {"id": "act_3576573649250348", "nome": "Dr. Flavius Cabral",  "orcamento": 5000.00},
    {"id": "act_738374729246811",  "nome": "Dr. Paulo Marcelo",   "orcamento": 1500.00},
    {"id": "act_1156389769838649", "nome": "Dra. Camila Firme",   "orcamento": 4500.00},
    {"id": "act_1493835775014316", "nome": "GO Advogados",        "orcamento": 5000.00},
]


# ──────────────────────────────────────────────
# BUSCAR GASTO
# ──────────────────────────────────────────────
def get_spend(account_id, date_start, date_end):
    url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
    params = {
        "access_token": META_ACCESS_TOKEN,
        "fields": "spend",
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "level": "account",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json().get("data", [])
    return float(data[0].get("spend", 0)) if data else 0.0


# ──────────────────────────────────────────────
# STATUS
# ──────────────────────────────────────────────
def get_status(pct_saldo):
    if pct_saldo <= 30:
        return "🔴"
    elif pct_saldo <= 40 and not NA_SEGUNDA_METADE:
        return "🟡"
    elif pct_saldo > 50 and NA_SEGUNDA_METADE:
        return "🟢"
    else:
        return "🟢"


# ──────────────────────────────────────────────
# BLOCO DE CADA CONTA
# ──────────────────────────────────────────────
def build_account_block(conta):
    nome = conta["nome"]
    orcamento = conta["orcamento"]
    account_id = conta["id"]

    gasto_semana = get_spend(account_id, SEMANA_INICIO, SEMANA_FIM)
    gasto_mes = get_spend(account_id, MES_INICIO_STR, MES_FIM_STR)

    saldo_restante = orcamento - gasto_mes
    pct_saldo = (saldo_restante / orcamento * 100) if orcamento > 0 else 0
    media_diaria = gasto_mes / DIAS_PASSADOS if DIAS_PASSADOS > 0 else 0
    dias_ate_zerar = (saldo_restante / media_diaria) if media_diaria > 0 else 999
    vai_durar = dias_ate_zerar >= DIAS_RESTANTES
    orcamento_ideal = round(saldo_restante / DIAS_RESTANTES, 2) if DIAS_RESTANTES > 0 else 0

    status = get_status(pct_saldo)
    alerta_critico = pct_saldo <= 30 and DIAS_RESTANTES <= 7

    lines = [
        f"{status} {nome}",
        f"Últimos 7 dias: R$ {gasto_semana:,.2f}  |  Média/dia: R$ {media_diaria:,.2f}",
        f"Acumulado ({MES_NOME}): R$ {gasto_mes:,.2f}",
        f"Saldo: R$ {saldo_restante:,.2f} ({pct_saldo:.0f}%) | Dias restantes: {DIAS_RESTANTES}",
    ]

    if vai_durar:
        lines.append("Projeção: saldo suficiente até o fim do mês ✅")
    else:
        lines.append(f"Projeção: saldo se esgota em ~{dias_ate_zerar:.0f} dias ⚠️")
        lines.append(f"Sugestão: reduzir orçamento diário para R$ {orcamento_ideal:,.2f}/dia")

    if alerta_critico:
        lines.append(f"🚨 ALERTA CRÍTICO: saldo crítico com {DIAS_RESTANTES} dias restantes!")

    if ALERTA_RECARGA_ATIVO:
        lines.append(f"🔔 RECARGA: solicitar boleto — faltam {DIAS_RESTANTES} dias para encerrar o mês")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# ENVIAR TELEGRAM
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
    cabecalho = (
        f"💰 RELATÓRIO DE INVESTIMENTOS\n"
        f"{MES_NOME} | {TODAY.strftime('%d/%m/%Y')}\n"
        f"Dias passados: {DIAS_PASSADOS} | Dias restantes: {DIAS_RESTANTES}"
    )
    send_telegram(cabecalho)
    print("Cabeçalho enviado.")

    for conta in CONTAS:
        print(f"Processando {conta['nome']}...")
        try:
            block = build_account_block(conta)
            send_telegram(block)
            time.sleep(1)
        except Exception as e:
            send_telegram(f"Erro ao processar {conta['nome']}:\n{str(e)}")

    print("Relatório enviado!")
