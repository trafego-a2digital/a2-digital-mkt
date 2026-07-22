# metas_pacing.py
# Módulo de pacing contra meta mensal de faturamento por conta — versão semanal.
# A bonificação exige DUAS coisas ao mesmo tempo: bater a meta de faturamento
# E manter ROAS >= 5 no mês. Por isso o status (bolinha) considera as duas.
#
# Uso no relatorio_semanal_metas.py:
#
#   from metas_pacing import bloco_meta_semanal
#   ...
#   msg += bloco_meta_semanal(account_id, receita_acumulada_mes, roas_mes)

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

ROAS_MINIMO = 5.0


def _fmt(valor: float) -> str:
    """Formata em R$ no padrão brasileiro, sem centavos."""
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def bloco_meta_semanal(
    account_id: str,
    receita_acumulada_mes: float,
    roas_mes: float,
    hoje: date | None = None,
) -> str:
    """Retorna o bloco de pacing vs meta para o relatório semanal (seg/qua/sex).

    Mostra meta, realizado, projeção, ROAS do mês, em quantos dias a meta é
    batida no ritmo atual, e recomendação quando estiver fora do ritmo.

    O status (bolinha) considera meta de faturamento E ROAS >= 5 ao mesmo
    tempo, porque a bonificação só vale se as duas condições forem atendidas:

    ✅  meta já batida E ROAS >= 5 (bonificação garantida se mantiver o ritmo)
    🟢  projeção bate a meta E ROAS >= 5 (no caminho certo nas duas frentes)
    🟡  só uma das duas está encaminhada (meta OU ROAS, não as duas)
    🔴  nem a meta nem o ROAS estão encaminhados

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

    meta_batida = receita_acumulada_mes >= meta
    meta_no_caminho = projecao >= meta
    roas_ok = roas_mes >= ROAS_MINIMO

    # Status combinando meta de faturamento e ROAS
    if meta_batida and roas_ok:
        status = "✅"
    elif meta_no_caminho and roas_ok:
        status = "🟢"
    elif meta_no_caminho or roas_ok:
        status = "🟡"
    else:
        status = "🔴"

    linhas = [
        "",
        f"{status} Meta do mês: {_fmt(meta)}",
        f"• Realizado: {_fmt(receita_acumulada_mes)} ({pct_meta:.0f}%)",
        f"• Projeção no ritmo atual: {_fmt(projecao)}",
        f"• ROAS do mês: {roas_mes:.2f}" + ("" if roas_ok else f" (abaixo do mínimo de {ROAS_MINIMO:.0f})"),
    ]

    if meta_batida:
        linhas.append(f"• Meta de faturamento batida com {dias_restantes} dia(s) de sobra no mês")
    else:
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

        if necessario_dia > media_diaria:
            if media_diaria > 0:
                aumento_pct = (necessario_dia / media_diaria - 1) * 100
                linhas.append(
                    f"⚠️ Ação: aumente a média diária em ~{aumento_pct:.0f}% "
                    f"(via orçamento e/ou ROAS) para bater a meta no prazo"
                )
            else:
                linhas.append("⚠️ Ação: conta zerada no mês, revisar campanhas ativas com urgência")

    # Alerta específico de ROAS, mesmo quando a meta de faturamento está ok:
    # sem ROAS >= 5 a bonificação não vale, independente do faturamento batido.
    if not roas_ok:
        linhas.append(f"⚠️ ROAS abaixo de {ROAS_MINIMO:.0f} — sem isso não há bonificação, mesmo com meta batida")

    return "\n".join(linhas)
