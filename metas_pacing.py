# metas_pacing.py
# Módulo de pacing contra meta mensal de faturamento por conta.
# Uso no roas_report.py:
#
#   from metas_pacing import bloco_meta
#   ...
#   # onde monta a mensagem de cada conta, depois do acumulado do mês:
#   msg += bloco_meta(account_id, receita_acumulada_mes)
#
# receita_acumulada_mes = faturamento (purchase value) acumulado do dia 1 até ontem.

from datetime import date, timedelta
import calendar

# Metas mínimas de faturamento por conta e por mês (bonificação exige também ROAS >= 5).
# Chave: ad account id sem o prefixo "act_". Mês: 1-12. Sem entrada = sem meta no mês.
METAS = {
    "1123910629201094": {7: 50000, 8: 50000, 9: 50000, 10: 100000, 11: 50000, 12: 50000},  # 16CIF
    "928960755916597":  {7: 20000, 8: 20000, 9: 20000, 10: 20000,  11: 20000, 12: 20000},  # Interpilates
    "565062448809883":  {7: 30000, 8: 30000, 9: 40000, 10: 30000,  11: 30000, 12: 30000},  # CONIFIC
    "1679280069737129": {7: 20000, 8: 20000, 9: 20000, 10: 20000,  11: 20000, 12: 20000},  # CARDIO
    "700954712494713":  {7: 30000, 8: 30000, 9: 30000, 10: 40000,  11: 20000, 12: 20000},  # CBFD
    "2352951311846960": {7: 15000, 8: 20000, 9: 20000, 10: 20000,  11: 20000, 12: 20000},  # CONSULFISIO
    "1378989810350371": {7: 20000, 8: 20000, 9: 20000, 10: 20000,  11: 20000, 12: 20000},  # INTERFITO
    "892752402026712":  {8: 10000, 9: 10000, 10: 10000, 11: 10000, 12: 10000},             # CONFIDEFE 11
}


def _fmt(valor: float) -> str:
    """Formata em R$ no padrão brasileiro, sem centavos."""
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def bloco_meta(account_id: str, receita_acumulada_mes: float, hoje: date | None = None) -> str:
    """Retorna as linhas de pacing vs meta para anexar à mensagem da conta.

    Considera que a receita acumulada vai até ontem (D-1), padrão do relatório.
    Retorna string vazia se a conta não tem meta no mês corrente.
    """
    hoje = hoje or date.today()
    account_id = account_id.replace("act_", "")
    meta = METAS.get(account_id, {}).get(hoje.month)
    if not meta:
        return ""

    ontem = hoje - timedelta(days=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]

    # Se o relatório roda dia 1, ontem pertence ao mês anterior: mês zerado.
    if ontem.month != hoje.month:
        dias_decorridos = 0
        dias_restantes = dias_no_mes
    else:
        dias_decorridos = ontem.day
        dias_restantes = dias_no_mes - dias_decorridos

    if dias_decorridos > 0:
        projecao = receita_acumulada_mes / dias_decorridos * dias_no_mes
    else:
        projecao = 0.0

    pct_meta = receita_acumulada_mes / meta * 100
    falta = max(meta - receita_acumulada_mes, 0)
    necessario_dia = falta / dias_restantes if dias_restantes > 0 else falta

    if receita_acumulada_mes >= meta:
        status = "✅"
    elif projecao >= meta:
        status = "🟢"
    elif projecao >= meta * 0.8:
        status = "🟡"
    else:
        status = "🔴"

    linhas = [
        "",
        f"{status} Meta do mês: {_fmt(meta)}",
        f"• Realizado: {_fmt(receita_acumulada_mes)} ({pct_meta:.0f}%)",
        f"• Projeção: {_fmt(projecao)}",
    ]
    if receita_acumulada_mes < meta:
        linhas.append(f"• Falta: {_fmt(falta)} ({_fmt(necessario_dia)}/dia em {dias_restantes} dias)")
    return "\n".join(linhas)
