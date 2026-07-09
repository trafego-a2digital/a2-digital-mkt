# metas_pacing.py
# Módulo de pacing contra meta mensal de faturamento por conta — versão semanal.
# Substitui o bloco antigo do relatório diário (bloco_meta) por bloco_meta_semanal,
# pensado para rodar segunda, quarta e sexta.
#
# Uso no roas_report.py (ou no script do relatório semanal):
#
#   from metas_pacing import bloco_meta_semanal
#   ...
#   msg += bloco_meta_semanal(account_id, receita_acumulada_mes)
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


def bloco_meta_semanal(account_id: str, receita_acumulada_mes: float, hoje: date | None = None) -> str:
    """Retorna o bloco de pacing vs meta para o relatório semanal (seg/qua/sex).

    Além do que o relatório diário já mostrava (meta, realizado, projeção, falta),
    inclui:
    - em quantos dias a meta é batida se o ritmo atual (média diária real) se mantiver
    - se está fora do ritmo, quanto precisa aumentar a média diária e uma recomendação

    Considera que a receita acumulada vai até ontem (D-1).
    Retorna string vazia se a conta não tem meta no mês corrente.
    """
    hoje = hoje or date.today()
    account_id = account_id.replace("act_", "")
    meta = METAS.get(account_id, {}).get(hoje.month)
    if not meta:
        return ""

    ontem = hoje - timedelta(days=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]

    if ontem.month != hoje.month:
        dias_decorridos = 0
        dias_restantes = dias_no_mes
    else:
        dias_decorridos = ontem.day
        dias_restantes = dias_no_mes - dias_decorridos

    media_diaria = receita_acumulada_mes / dias_decorridos if dias_decorridos > 0 else 0.0
    projecao = media_diaria * dias_no_mes
    falta = max(meta - receita_acumulada_mes, 0)
    necessario_dia = falta / dias_restantes if dias_restantes > 0 else falta
    pct_meta = receita_acumulada_mes / meta * 100

    # Status
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
        f"• Projeção no ritmo atual: {_fmt(projecao)}",
    ]

    if receita_acumulada_mes >= meta:
        linhas.append(f"• Meta batida com {dias_restantes} dia(s) de sobra no mês")
        return "\n".join(linhas)

    # Em quantos dias bate a meta no ritmo atual (média diária real desde o dia 1)
    if media_diaria > 0:
        dias_para_bater = meta / media_diaria
        if dias_para_bater <= dias_no_mes:
            dia_previsto = dias_para_bater - dias_decorridos
            linhas.append(f"• No ritmo atual, bate a meta em ~{dia_previsto:.0f} dia(s)")
        else:
            linhas.append("• No ritmo atual, NÃO bate a meta dentro do mês")
    else:
        linhas.append("• Sem vendas registradas no mês até agora")

    linhas.append(f"• Falta: {_fmt(falta)} ({_fmt(necessario_dia)}/dia em {dias_restantes} dias restantes)")

    # Recomendação de ação quando o ritmo atual não é suficiente
    if necessario_dia > media_diaria:
        if media_diaria > 0:
            aumento_pct = (necessario_dia / media_diaria - 1) * 100
            linhas.append(
                f"⚠️ Ação: aumente a média diária em ~{aumento_pct:.0f}% "
                f"(via orçamento e/ou ROAS) para bater a meta no prazo"
            )
        else:
            linhas.append("⚠️ Ação: conta zerada no mês, revisar campanhas ativas com urgência")

    return "\n".join(linhas)
