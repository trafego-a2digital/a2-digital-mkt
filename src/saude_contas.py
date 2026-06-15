"""
saude_contas.py — Automação 4
Verificação diária de saúde de cada conta:
  🛑 Conta desativada / com restrição (account_status != 1)
  ❌ Anúncios reprovados (DISAPPROVED) — com motivo, quando disponível
  ⚠️ Anúncios com problemas (WITH_ISSUES)
  ⏳ Anúncios em revisão há mais tempo (PENDING_REVIEW) — informativo
Alerta imediato no Telegram. Silencioso quando está tudo ok.
Execução sugerida: diária, 07h15 Brasília (logo após o alerta de anomalias).
"""

from comum import (carregar_config, status_conta, anuncios_com_problema,
                   enviar_telegram)

STATUS_CONTA = {
    1: None,  # ativa — sem alerta
    2: "DESATIVADA",
    3: "NÃO CONFIRMADA",
    7: "EM ANÁLISE (risco de pagamento)",
    9: "EM PERÍODO DE CARÊNCIA",
    100: "PENDENTE DE FECHAMENTO",
    101: "FECHADA",
}

ICONE_STATUS_AD = {
    "DISAPPROVED": "❌",
    "WITH_ISSUES": "⚠️",
    "PENDING_REVIEW": "⏳",
}


def analisar_conta(conta):
    alertas = []

    # 1. Status da conta
    info = status_conta(conta["account_id"])
    if "erro" in info:
        return [f"❌ Erro na API: {info['erro'].get('message', '?')[:150]}"]
    st = info.get("account_status")
    rotulo = STATUS_CONTA.get(st, f"STATUS {st}")
    if rotulo:
        alertas.append(f"🛑 <b>CONTA {rotulo}</b>"
                       + (f" — motivo: {info.get('disable_reason')}" if info.get("disable_reason") else ""))

    # 2. Anúncios com problema
    ads, erro = anuncios_com_problema(conta["account_id"])
    if erro:
        alertas.append(f"❌ Erro ao listar anúncios: {erro.get('message', '?')[:150]}")
        return alertas

    por_status = {}
    for ad in ads:
        por_status.setdefault(ad.get("effective_status"), []).append(ad)

    for st_ad in ("DISAPPROVED", "WITH_ISSUES"):
        for ad in por_status.get(st_ad, []):
            camp = (ad.get("campaign") or {}).get("name", "?")
            linha = f"{ICONE_STATUS_AD[st_ad]} <b>{ad.get('name', '?')}</b> ({camp})"
            feedback = ad.get("ad_review_feedback") or {}
            motivos = feedback.get("global") or {}
            if motivos:
                linha += f"\n      Motivo: {'; '.join(list(motivos.keys())[:2])}"
            alertas.append(linha)

    pendentes = por_status.get("PENDING_REVIEW", [])
    if pendentes:
        alertas.append(f"⏳ {len(pendentes)} anúncio(s) em revisão")

    return alertas


def main():
    cfg = carregar_config()
    blocos = []

    for conta in cfg["contas"]:
        if not conta.get("ativo", True):
            continue
        alertas = analisar_conta(conta)
        if alertas:
            blocos.append(f"\n📊 <b>{conta['nome'].upper()}</b>\n" + "\n".join(alertas))

    if blocos:
        msg = "🏥 <b>SAÚDE DAS CONTAS — META ADS</b>\n" + "\n".join(blocos)
        enviar_telegram(msg)
    else:
        print("Todas as contas saudáveis. Nenhum anúncio com problema.")


if __name__ == "__main__":
    main()
