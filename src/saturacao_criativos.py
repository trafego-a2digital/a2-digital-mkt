"""
saturacao_criativos.py — Automação 2
Detecta criativos saturando, por anúncio ativo:
  - Frequência (últimos 7 dias) acima do limite (padrão 3.0)
  - CTR dos últimos 7 dias caiu X% vs os 7 dias anteriores (padrão -30%)
Marca cada criativo com nível:
  🔴 Saturado (frequência alta E CTR em queda) → trocar
  🟡 Atenção (apenas um dos dois sinais) → preparar substituto
Execução sugerida: 2x por semana (segunda e quinta, 07h30 Brasília).
"""

from datetime import timedelta
from comum import (carregar_config, insights_conta, extrair_resultados,
                   hoje_br, enviar_telegram, fmt_brl)

FIELDS_AD = ["ad_id", "ad_name", "campaign_name", "spend",
             "impressions", "clicks", "ctr", "frequency", "actions"]


def metricas_ads(account_id, since, until, gasto_min):
    linhas, erro = insights_conta(account_id, since, until,
                                  level="ad", fields=FIELDS_AD)
    if erro:
        return None, erro
    ads = {}
    for ln in linhas:
        gasto = float(ln.get("spend", 0) or 0)
        if gasto < gasto_min:
            continue
        ads[ln["ad_id"]] = {
            "nome": ln.get("ad_name", "?"),
            "campanha": ln.get("campaign_name", "?"),
            "gasto": gasto,
            "ctr": float(ln.get("ctr", 0) or 0),
            "freq": float(ln.get("frequency", 0) or 0),
            "resultados": extrair_resultados(ln),
        }
    return ads, None


def analisar_conta(conta, limites):
    hoje = hoje_br()
    # Janela atual: últimos 7 dias | Janela anterior: 7 dias antes disso
    atual_ini, atual_fim = hoje - timedelta(days=7), hoje - timedelta(days=1)
    ant_ini, ant_fim = hoje - timedelta(days=14), hoje - timedelta(days=8)
    gasto_min = limites["gasto_minimo_analise"]

    atual, erro1 = metricas_ads(conta["account_id"], atual_ini, atual_fim, gasto_min)
    anterior, erro2 = metricas_ads(conta["account_id"], ant_ini, ant_fim, 0)
    if erro1 or erro2:
        return [f"❌ <b>{conta['nome']}</b>: erro na API — "
                f"{(erro1 or erro2).get('message', '?')[:150]}"]

    saturados, atencao = [], []

    for ad_id, ad in atual.items():
        freq_alta = ad["freq"] >= limites["frequencia_saturacao"]

        ctr_caiu = False
        var_ctr = None
        ant = anterior.get(ad_id)
        if ant and ant["ctr"] > 0:
            var_ctr = (ad["ctr"] - ant["ctr"]) / ant["ctr"] * 100
            ctr_caiu = var_ctr <= -limites["queda_ctr_saturacao_pct"]

        if not freq_alta and not ctr_caiu:
            continue

        detalhe = (f"<b>{ad['nome']}</b>\n"
                   f"   Campanha: {ad['campanha']}\n"
                   f"   Freq 7d: {ad['freq']:.1f} · CTR: {ad['ctr']:.2f}%"
                   + (f" ({var_ctr:+.0f}% vs semana anterior)" if var_ctr is not None else "")
                   + f" · Gasto 7d: {fmt_brl(ad['gasto'])}")

        if freq_alta and ctr_caiu:
            saturados.append("🔴 " + detalhe + "\n   → <b>Trocar criativo</b>")
        else:
            motivo = "frequência alta" if freq_alta else "CTR em queda"
            atencao.append("🟡 " + detalhe + f"\n   → Preparar substituto ({motivo})")

    return saturados + atencao


def main():
    cfg = carregar_config()
    limites = cfg["limites"]
    blocos = []

    for conta in cfg["contas"]:
        if not conta.get("ativo", True):
            continue
        achados = analisar_conta(conta, limites)
        if achados:
            blocos.append(f"\n📊 <b>{conta['nome'].upper()}</b>\n" + "\n\n".join(achados))

    if blocos:
        msg = ("🎨 <b>SATURAÇÃO DE CRIATIVOS — META ADS</b>\n"
               "<i>Últimos 7 dias vs 7 dias anteriores</i>\n"
               + "\n".join(blocos))
        enviar_telegram(msg)
    else:
        print("Nenhum criativo saturando. Tudo ok.")


if __name__ == "__main__":
    main()
