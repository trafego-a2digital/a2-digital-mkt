"""
alerta_anomalias.py — Automação 1
Compara ONTEM contra a média diária dos 14 dias anteriores, por campanha.
Alerta no Telegram apenas quando algo foge do padrão:
  ⚠️ CPL/CPR subiu acima do limite configurado
  💸 Gasto diário acelerou acima do limite
  🛑 Campanha que gastava e zerou a entrega
Execução sugerida: diária, 07h00 Brasília.
"""

from datetime import timedelta
from comum import (carregar_config, metricas_periodo, hoje_br,
                   enviar_telegram, fmt_brl)


def analisar_conta(conta, limites):
    hoje = hoje_br()
    ontem = hoje - timedelta(days=1)
    base_ini = hoje - timedelta(days=15)
    base_fim = hoje - timedelta(days=2)
    dias_base = 14

    atual, erro1 = metricas_periodo(conta["account_id"], ontem, ontem)
    base, erro2 = metricas_periodo(conta["account_id"], base_ini, base_fim)
    if erro1 or erro2:
        return [f"❌ <b>{conta['nome']}</b>: erro na API — "
                f"{(erro1 or erro2).get('message', '?')[:150]}"]

    base_por_camp = {c["id"]: c for c in base}
    atual_por_camp = {c["id"]: c for c in atual}
    alertas = []

    for cid, c in atual_por_camp.items():
        b = base_por_camp.get(cid)
        if not b or b["gasto"] < limites["gasto_minimo_analise"]:
            continue

        gasto_medio_dia = b["gasto"] / dias_base
        cpr_base = (b["gasto"] / b["resultados"]) if b["resultados"] else None

        # Gasto acelerado
        if gasto_medio_dia > 0:
            var_gasto = (c["gasto"] - gasto_medio_dia) / gasto_medio_dia * 100
            if var_gasto >= limites["variacao_gasto_alerta_pct"]:
                alertas.append(
                    f"💸 <b>{c['nome']}</b>\n"
                    f"   Gasto ontem: {fmt_brl(c['gasto'])} "
                    f"(média 14d: {fmt_brl(gasto_medio_dia)}/dia → +{var_gasto:.0f}%)")

        # CPR estourando
        if cpr_base and c["cpr"]:
            var_cpr = (c["cpr"] - cpr_base) / cpr_base * 100
            if var_cpr >= limites["variacao_cpl_alerta_pct"]:
                alertas.append(
                    f"⚠️ <b>{c['nome']}</b>\n"
                    f"   CPR ontem: {fmt_brl(c['cpr'])} "
                    f"(média 14d: {fmt_brl(round(cpr_base, 2))} → +{var_cpr:.0f}%)")

        # Gastou mas zerou resultados (e a base tinha resultados)
        if c["gasto"] >= limites["gasto_minimo_analise"] and c["resultados"] == 0 \
                and b["resultados"] > 0:
            alertas.append(
                f"🚨 <b>{c['nome']}</b>\n"
                f"   Gastou {fmt_brl(c['gasto'])} ontem SEM nenhum resultado "
                f"(base 14d: {b['resultados']} resultados)")

    # Campanha que gastava na base e zerou entrega ontem
    for cid, b in base_por_camp.items():
        if cid not in atual_por_camp and (b["gasto"] / dias_base) >= limites["gasto_minimo_analise"]:
            alertas.append(
                f"🛑 <b>{b['nome']}</b>\n"
                f"   Sem entrega ontem (gastava {fmt_brl(round(b['gasto'] / dias_base, 2))}/dia). "
                f"Verificar se foi pausada de propósito.")

    return alertas


def main():
    cfg = carregar_config()
    limites = cfg["limites"]
    blocos = []

    for conta in cfg["contas"]:
        if not conta.get("ativo", True):
            continue
        alertas = analisar_conta(conta, limites)
        if alertas:
            blocos.append(f"\n📊 <b>{conta['nome'].upper()}</b>\n" + "\n".join(alertas))

    if blocos:
        msg = "🔔 <b>ALERTA DE ANOMALIAS — META ADS</b>\n" \
              f"<i>Ontem vs média dos últimos 14 dias</i>\n" + "\n".join(blocos)
        enviar_telegram(msg)
    else:
        # Silencioso quando está tudo ok — só loga no Actions
        print("Nenhuma anomalia detectada. Tudo dentro do padrão.")


if __name__ == "__main__":
    main()
