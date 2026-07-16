"""
dados_relatorio_semanal.py — Automação 3 (versão com relatório completo)
Duas execuções por semana, cada uma com seu próprio grupo de contas:
  - Segunda-feira, 08h00 Brasília: Clay e Tiago, enviados ao chat/grupo padrão
  - Quarta-feira,  08h00 Brasília: Flavius, enviado ao chat pessoal do Wesley
Para cada conta processada no dia:
  1. Puxa dados dos últimos 7 dias completos antes da execução
  2. Busca link de prévia compartilhável de cada criativo (Graph API)
  3. Gera o HTML no layout oficial do Relatório A2, com a logo da pasta
     assets/ embutida em base64
  4. Envia ao Telegram: resumo executivo + arquivo .html pronto
     (abrir no Chrome → Salvar como PDF com "Gráficos de fundo" ativado)
"""

import json
import os
from datetime import datetime, timedelta, timezone
from comum import (carregar_config, metricas_periodo, insights_conta,
                   extrair_resultados, detalhes_anuncio, hoje_br,
                   enviar_telegram, enviar_documento_telegram, fmt_brl)
from gerar_html_a2 import gerar_html, carregar_logo_b64

FIELDS_AD = ["ad_id", "ad_name", "campaign_id", "campaign_name",
             "spend", "impressions", "clicks", "ctr", "actions"]


def periodo_ultimos_7_dias():
    """Retorna (inicio, fim) cobrindo os últimos 7 dias completos
    antes da data de execução. Funciona independente do dia da semana
    em que o workflow rodar."""
    hoje = hoje_br()
    fim = hoje - timedelta(days=1)
    inicio = fim - timedelta(days=6)
    return inicio, fim


def top_criativos(account_id, since, until, gasto_min, top_n=3):
    linhas, erro = insights_conta(account_id, since, until,
                                  level="ad", fields=FIELDS_AD)
    if erro:
        return {}, erro
    por_campanha = {}
    for ln in linhas:
        gasto = float(ln.get("spend", 0) or 0)
        if gasto < gasto_min:
            continue
        item = {
            "ad_id": ln.get("ad_id"),
            "nome": ln.get("ad_name", "?"),
            "gasto": round(gasto, 2),
            "impressoes": int(ln.get("impressions", 0) or 0),
            "cliques": int(ln.get("clicks", 0) or 0),
            "ctr": float(ln.get("ctr", 0) or 0),
            "resultados": extrair_resultados(ln),
        }
        item["cpr"] = round(gasto / item["resultados"], 2) if item["resultados"] else None
        por_campanha.setdefault(ln.get("campaign_id"), []).append(item)

    limite_novo = datetime.now(timezone.utc) - timedelta(days=7)
    for cid in por_campanha:
        por_campanha[cid].sort(key=lambda a: (-a["resultados"],
                                              a["cpr"] if a["cpr"] else 9e9))
        por_campanha[cid] = por_campanha[cid][:top_n]
        # Prévia + badge "Novo" só para os tops (poupa chamadas de API)
        for cr in por_campanha[cid]:
            det = detalhes_anuncio(cr["ad_id"])
            cr["preview"] = det.get("preview_shareable_link")
            criado = det.get("created_time")
            cr["novo"] = False
            if criado:
                try:
                    dt = datetime.fromisoformat(criado.replace("+0000", "+00:00"))
                    cr["novo"] = dt >= limite_novo
                except ValueError:
                    pass
    return por_campanha, None


def processar_conta(conta, limites, since, until, pasta_saida, logo_b64):
    campanhas, erro = metricas_periodo(conta["account_id"], since, until)
    if erro:
        return None, None, (f"❌ <b>{conta['nome']}</b>: erro na API — "
                            f"{erro.get('message', '?')[:150]}")

    criativos, _ = top_criativos(conta["account_id"], since, until,
                                 limites["gasto_minimo_analise"])

    total_gasto = sum(c["gasto"] for c in campanhas)
    total_res = sum(c["resultados"] for c in campanhas)
    cpr_medio = round(total_gasto / total_res, 2) if total_res else None

    payload = {
        "cliente": conta["nome"],
        "account_id": conta["account_id"],
        "periodo": {"inicio": str(since), "fim": str(until), "tipo": "semanal"},
        "totais": {"investido": round(total_gasto, 2),
                   "resultados": total_res, "cpr_medio": cpr_medio},
        "campanhas": [
            {**c, "top_criativos": criativos.get(c["id"], [])}
            for c in sorted(campanhas, key=lambda x: (x["cpr"] is None, x["cpr"] or 0))
        ],
    }

    slug = conta["nome"].lower().split()[-1]
    semana = since.strftime("%d%b").lower()

    caminho_json = os.path.join(pasta_saida, f"dados_{slug}_{since}.json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    caminho_html = os.path.join(pasta_saida, f"relatorio_{slug}_semana{semana}.html")
    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write(gerar_html(payload, logo_b64))

    melhor = min((c for c in campanhas if c["cpr"]), key=lambda c: c["cpr"], default=None)
    linhas = [f"\n📊 <b>{conta['nome'].upper()}</b>",
              f"   Investido: {fmt_brl(total_gasto)} · Resultados: {total_res} · "
              f"CPR médio: {fmt_brl(cpr_medio)}"]
    if melhor:
        linhas.append(f"   ✅ Melhor CPR: {melhor['nome']} — {fmt_brl(melhor['cpr'])}")
    return caminho_html, caminho_json, "\n".join(linhas)


# Slugs (última palavra do nome, em minúsculo) que rodam em cada dia.
# Segunda: Clay e Tiago. Quarta: só o Flavius.
# Todos os três (Clay, Tiago, Flavius) vão para o mesmo grupo do Telegram
# (TELEGRAM_CHAT_ID = grupo "Relatorios semanais Clay - A2 Digital Mkt").
CONTAS_SEGUNDA = {"clay", "tiago"}
CONTAS_QUARTA = {"flavius"}


def dia_de_execucao():
    """Descobre qual gatilho disparou o workflow.
    Prioriza o cron exato (github.event.schedule); se rodar via
    workflow_dispatch (manual) ou fora do Actions, cai pro dia da
    semana real em Brasília."""
    evento = os.environ.get("GITHUB_EVENT_SCHEDULE", "").strip()
    if evento == "0 11 * * 3":
        return "quarta"
    if evento == "0 11 * * 1":
        return "segunda"
    return "quarta" if hoje_br().weekday() == 2 else "segunda"


def main():
    cfg = carregar_config()
    since, until = periodo_ultimos_7_dias()
    pasta = os.environ.get("PASTA_SAIDA", "/tmp/relatorios")
    os.makedirs(pasta, exist_ok=True)

    dia = dia_de_execucao()
    slugs_do_dia = CONTAS_QUARTA if dia == "quarta" else CONTAS_SEGUNDA
    contas_do_dia = [c for c in cfg["contas"]
                     if c["nome"].lower().split()[-1] in slugs_do_dia]

    logo_b64 = carregar_logo_b64(cfg.get("logo_path", "assets/logo.png"))
    if not logo_b64:
        print("[AVISO] Logo não encontrada em assets/ — relatório sai com texto no lugar.")

    blocos, htmls = [], []
    for conta in contas_do_dia:
        if not conta.get("ativo", True):
            continue
        html, _json, resumo = processar_conta(conta, cfg["limites"],
                                              since, until, pasta, logo_b64)
        blocos.append(resumo)
        if html:
            htmls.append((html, conta["nome"]))

    cab = (f"📅 <b>RELATÓRIOS SEMANAIS — META ADS</b>\n"
           f"<i>Período: {since.strftime('%d/%m')} a {until.strftime('%d/%m')}</i>\n"
           f"<i>HTMLs em anexo — abrir no Chrome e Salvar como PDF "
           f"com \"Gráficos de fundo\" ativado.</i>\n")

    enviar_telegram(cab + "\n".join(blocos))

    for caminho, nome in htmls:
        enviar_documento_telegram(caminho, legenda=f"Relatório A2 — {nome}")


if __name__ == "__main__":
    main()
