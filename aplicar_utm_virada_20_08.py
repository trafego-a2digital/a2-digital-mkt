#!/usr/bin/env python3
"""
Aplica UTM (url_tags) nos 39 anuncios da virada de lote 20/08 (16CIF).

Por que via script: a Graph API do Meta aceita o campo `url_tags` direto
no objeto do Anuncio via POST /{ad_id}, mas isso nao muda o link_url visivel
no anuncio - so anexa os parametros na hora do clique. E o mesmo campo que
aparece em "Rastreamento > Parametros de URL" no Gerenciador de Anuncios.

A UTM ja vem fixa no codigo (constante UTM_STRING logo abaixo). Nao precisa
passar --utm na linha de comando a menos que queira usar outra, pontualmente.

Uso:
    export FB_ACCESS_TOKEN="seu_token_de_system_user"
    python aplicar_utm_virada_20_08.py --dry-run
    python aplicar_utm_virada_20_08.py

No GitHub Actions, passe o token como secret (ex: secrets.FB_ACCESS_TOKEN).
Nao ha necessidade de passar a UTM como input do workflow, ja que ela esta
fixa no codigo - isso tambem evita qualquer conflito entre os macros {{ }}
da UTM e a sintaxe de interpolacao ${{ }} do proprio GitHub Actions.
"""

import argparse
import os
import sys
import time

import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# UTM padrao da virada 20/08 (16CIF). Usa os macros dinamicos do Meta
# ({{campaign.name}}, {{ad.id}}, etc.), preenchidos automaticamente pelo
# proprio Meta a cada impressao/clique - nao sao placeholders pra voce trocar.
UTM_STRING = (
    "utm_source=FB"
    "&utm_campaign={{campaign.name}}|{{campaign.id}}"
    "&utm_medium={{adset.name}}|{{adset.id}}"
    "&utm_content={{ad.name}}|{{ad.id}}"
    "&utm_term={{placement}}"
)

# Os 39 anuncios da virada 20/08 (16CIF), com nome pra facilitar leitura do log.
# Ajuste esta lista se algum ID mudar ou se voce reaproveitar o script noutra virada.
ADS = [
    # --- Campanha Quente (18) ---
    ("120253644356790523", "01 - ADV - Quente - Video Human - S10_BRUNO"),
    ("120253644403930523", "02 - ADV - Quente - Video Human - S11_MARCO"),
    ("120253644405280523", "03 - ADV - Quente - Video Human - S12_THALISSA"),
    ("120253644406480523", "04 - ADV - Quente - Video Human - S13_THALISSA"),
    ("120253644408030523", "05 - ADV - Quente - Video Human - S14_FLAVIO"),
    ("120253644408910523", "06 - ADV - Quente - Video Human - S15_WORKSHOPS"),
    ("120253644409580523", "07 - ADI - Quente - Img Human - N2 feed"),
    ("120253644410710523", "08 - ADI - Quente - Img Human - N3 feed"),
    ("120253644411520523", "09 - ADI - Quente - Img Human - N4 feed"),
    ("120253644412570523", "10 - ADI - Quente - Img Human - N5 feed"),
    ("120253644413460523", "11 - ADI - Quente - Img Human - N6 feed"),
    ("120253644413900523", "12 - ADV - Quente - Video S01"),
    ("120253644414730523", "13 - ADV - Quente - Video S02"),
    ("120253644415140523", "14 - ADV - Quente - Video S03"),
    ("120253644416100523", "15 - ADV - Quente - Video S04"),
    ("120253644417450523", "16 - ADI - Quente - Img N1 feed"),
    ("120253644418870523", "17 - ADI - Quente - Img N9 feed"),
    ("120253644420280523", "18 - ADI - Quente - Img N10 feed"),
    # --- Campanha Aquisicao (11) ---
    ("120253644605720523", "01 - ADI - Aquisicao - Contexto - Luiz Severo"),
    ("120253644606280523", "02 - ADI - Aquisicao - Contexto - Ramon Martins"),
    ("120253644607690523", "03 - ADV - Aquisicao - Contexto - Centro de Eventos"),
    ("120253644608960523", "04 - ADV - Aquisicao - Contexto - proximo passo para o futuro"),
    ("120253644610610523", "05 - ADV - Aquisicao - Contexto - Leonardo Emery"),
    ("120253644611550523", "06 - ADV - Aquisicao - Contexto - Irlan Modesto"),
    ("120253644612720523", "07 - ADV - Aquisicao - Video Human - S16_MARIA"),
    ("120253644613890523", "08 - ADV - Aquisicao - Video Human - S13_THALISSA"),
    ("120253644615000523", "09 - ADV - Aquisicao - Video Human - S14_FLAVIO"),
    ("120253644616890523", "10 - ADV - Aquisicao - Video S07"),
    ("120253644617770523", "11 - ADV - Aquisicao - Video S08"),
    # --- Conjunto 3A - Cobertura (5) ---
    ("120253644619220523", "01 - ADV - 3A - Video S05"),
    ("120253644620660523", "02 - ADV - 3A - Video S06"),
    ("120253644621290523", "03 - ADI - 3A - Img N11 feed"),
    ("120253644622230523", "04 - ADI - 3A - Img N12 feed"),
    ("120253644623290523", "05 - ADI - 3A - Img N13 feed"),
    # --- Conjunto 3B - Ultima chamada (5) ---
    ("120253644625110523", "01 - ADV - 3B - Video Human - S15_WORKSHOPS"),
    ("120253644626080523", "02 - ADV - 3B - Video Human - S12_THALISSA"),
    ("120253644627290523", "03 - ADI - 3B - Img Human - N7 feed"),
    ("120253644627950523", "04 - ADI - 3B - Img N9 feed"),
    ("120253644628570523", "05 - ADI - 3B - Img N10 feed"),
]


def apply_utm(ad_id: str, ad_name: str, utm_string: str, access_token: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"[DRY-RUN] {ad_id}  {ad_name}  ->  url_tags={utm_string}")
        return True

    url = f"{GRAPH_API_BASE}/{ad_id}"
    resp = requests.post(
        url,
        data={
            "url_tags": utm_string,
            "access_token": access_token,
        },
        timeout=30,
    )

    if resp.status_code == 200 and resp.json().get("success", True):
        print(f"[OK]   {ad_id}  {ad_name}")
        return True

    print(f"[ERRO] {ad_id}  {ad_name}  ->  {resp.status_code} {resp.text}", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--utm",
        default=UTM_STRING,
        help="String de UTM sem o '?' inicial. Por padrao usa UTM_STRING definida no topo do arquivo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="So mostra o que seria feito, sem chamar a API de verdade.",
    )
    args = parser.parse_args()

    access_token = os.environ.get("META_ACCESS_TOKEN")
    if not access_token and not args.dry_run:
        print("Erro: defina a variavel de ambiente FB_ACCESS_TOKEN (ou use --dry-run).", file=sys.stderr)
        return 1

    ok_count = 0
    fail_count = 0

    for ad_id, ad_name in ADS:
        success = apply_utm(ad_id, ad_name, args.utm, access_token, args.dry_run)
        if success:
            ok_count += 1
        else:
            fail_count += 1
        time.sleep(0.5)  # evita bater no rate limit da API

    print(f"\nConcluido: {ok_count} ok, {fail_count} com erro, {len(ADS)} no total.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
