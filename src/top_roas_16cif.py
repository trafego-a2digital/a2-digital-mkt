"""
Puxa os anúncios da conta 16CIF (1123910629201094) ordenados por ROAS,
filtrando os que têm ROAS > 5. Usa o mesmo token de Marketing API que já
está configurado no repositório da A2 Digital.

Uso:
    export META_ACCESS_TOKEN="seu_token_aqui"
    pip install requests
    python top_roas_16cif.py

Ajuste ROAS_MINIMO e TOP_N se quiser outro corte.
"""

import os
import requests

AD_ACCOUNT_ID = "1123910629201094"
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
API_VERSION = "v21.0"
ROAS_MINIMO = 5
TOP_N = 10

if not ACCESS_TOKEN:
    raise SystemExit("Defina a variável de ambiente META_ACCESS_TOKEN antes de rodar.")


def buscar_insights_por_anuncio():
    url = f"https://graph.facebook.com/{API_VERSION}/act_{AD_ACCOUNT_ID}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "level": "ad",
        "date_preset": "maximum",  # lifetime
        "fields": "ad_id,ad_name,spend,action_values,purchase_roas",
        "limit": 500,
    }

    resultados = []
    while url:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        resultados.extend(data.get("data", []))

        paging = data.get("paging", {})
        url = paging.get("next")
        params = {}  # a URL "next" já vem com todos os parâmetros embutidos

    return resultados


def calcular_roas(registro):
    # 1) Usa purchase_roas nativo se o Meta já calculou
    purchase_roas = registro.get("purchase_roas")
    if purchase_roas:
        try:
            return float(purchase_roas[0]["value"])
        except (KeyError, IndexError, ValueError, TypeError):
            pass

    # 2) Fallback: soma action_values (valor de conversão) / spend
    spend = float(registro.get("spend", 0) or 0)
    if spend <= 0:
        return None

    action_values = registro.get("action_values", []) or []
    valor_total = sum(
        float(av.get("value", 0))
        for av in action_values
        if av.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase", "omni_purchase")
    )
    if valor_total <= 0:
        return None

    return valor_total / spend


def main():
    registros = buscar_insights_por_anuncio()

    anuncios_com_roas = []
    for registro in registros:
        roas = calcular_roas(registro)
        if roas is not None:
            anuncios_com_roas.append(
                {
                    "ad_id": registro.get("ad_id"),
                    "ad_name": registro.get("ad_name"),
                    "spend": float(registro.get("spend", 0) or 0),
                    "roas": roas,
                }
            )

    anuncios_com_roas.sort(key=lambda x: x["roas"], reverse=True)
    acima_do_corte = [a for a in anuncios_com_roas if a["roas"] > ROAS_MINIMO]
    top = acima_do_corte[:TOP_N]

    print(f"\nTotal de anúncios com dado de ROAS: {len(anuncios_com_roas)}")
    print(f"Anúncios com ROAS > {ROAS_MINIMO}: {len(acima_do_corte)}\n")
    print(f"Top {TOP_N} por ROAS:\n")
    for i, a in enumerate(top, start=1):
        print(f"{i:>2}. ROAS {a['roas']:.2f} | gasto R$ {a['spend']:.2f} | {a['ad_name']} (ID: {a['ad_id']})")

    if not top:
        print("Nenhum anúncio encontrado acima do corte de ROAS definido.")


if __name__ == "__main__":
    main()
