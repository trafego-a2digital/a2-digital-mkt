"""
relatorio_mensal_flavius.py — execução avulsa (fechamento mensal)

Gera o relatório A2 do Dr. Flávius para dois períodos, no mesmo layout/PDF
da Automação 3, sem depender do agendamento normal (segunda = Clay/Tiago,
quarta = Flavius):

  - 01/07/2026 a 31/07/2026  (fechamento de julho)
  - 01/08/2026 a 05/08/2026  (parcial de agosto, até a reunião de hoje)

Reaproveita 100% do pipeline já existente em dados_relatorio_semanal.py
(comum, gerar_html_a2, realocacao) — inclusive a realocação de campanhas
de contingência, se houver alguma nesses períodos. Só troca o período e o
nome de saída dos arquivos: em vez de "semanaDDmon" (formato semanal),
saem como "fechamento_jul2026" e "parcial_ago2026".

Uso:
  python relatorio_mensal_flavius.py

Requer as mesmas variáveis de ambiente/segredos já configurados para a
Automação 3 (token do Meta Ads, TELEGRAM_CHAT_ID_GRUPO ou o chat pessoal
do Wesley, contas.json, assets/logo.png). Rode local ou via
workflow_dispatch manual no GitHub Actions — este script não altera o
cron das automações existentes.
"""

import os
from datetime import date

from playwright.sync_api import sync_playwright

from comum import carregar_config, enviar_telegram, enviar_documento_telegram
from gerar_html_a2 import carregar_logo_b64
from realocacao import conta_por_slug
from dados_relatorio_semanal import processar_conta

# Ajuste aqui se o período da reunião mudar.
PERIODOS = [
    ("fechamento_jul2026", date(2026, 7, 1), date(2026, 7, 31)),
    ("parcial_ago2026", date(2026, 8, 1), date(2026, 8, 5)),
]

SLUG_CLIENTE = "flavius"

# Defina como False se quiser só gerar os arquivos localmente, sem mandar
# pro Telegram (por exemplo, pra revisar antes de enviar pro cliente).
ENVIAR_TELEGRAM = os.environ.get("ENVIAR_TELEGRAM", "1") == "1"


def renomear_saida(caminho, rotulo):
    """processar_conta() salva PDF/HTML/JSON com nome baseado em
    'semanaDDmon' (formato pensado pro relatório semanal) — aqui só
    troca esse sufixo pelo rótulo do fechamento mensal."""
    if not caminho:
        return None
    base, ext = os.path.splitext(caminho)
    prefixo = base.rsplit("_semana", 1)[0]
    novo = f"{prefixo}_{rotulo}{ext}"
    os.replace(caminho, novo)
    return novo


def main():
    cfg = carregar_config()
    pasta = os.environ.get("PASTA_SAIDA", "/tmp/relatorios")
    os.makedirs(pasta, exist_ok=True)

    conta = conta_por_slug(cfg, SLUG_CLIENTE)
    if not conta:
        raise SystemExit(
            f"[ERRO] Slug '{SLUG_CLIENTE}' não encontrado em contas.json."
        )

    logo_b64 = carregar_logo_b64(cfg.get("logo_path", "assets/logo.png"))
    if not logo_b64:
        print("[AVISO] Logo não encontrada em assets/ — relatório sai com texto no lugar.")

    blocos, pdfs = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for rotulo, since, until in PERIODOS:
            pdf, _json, resumo = processar_conta(
                conta, cfg, since, until, pasta, logo_b64, browser
            )
            pdf = renomear_saida(pdf, rotulo)
            cabecalho = (
                f"\n🗓️ <b>Período: {since.strftime('%d/%m')} "
                f"a {until.strftime('%d/%m')}</b>"
            )
            blocos.append(cabecalho + resumo)
            if pdf:
                pdfs.append((pdf, f"Dr. Flávius Cabral — {rotulo}"))
            print(f"[OK] {rotulo}: {pdf}")
        browser.close()

    if ENVIAR_TELEGRAM:
        enviar_telegram("📊 <b>RELATÓRIO MENSAL — DR. FLÁVIUS</b>\n" + "\n".join(blocos))
        for caminho, nome in pdfs:
            enviar_documento_telegram(caminho, legenda=f"Relatório A2 — {nome}")
    else:
        print("[INFO] ENVIAR_TELEGRAM=0 — arquivos gerados localmente, nada enviado.")


if __name__ == "__main__":
    main()
