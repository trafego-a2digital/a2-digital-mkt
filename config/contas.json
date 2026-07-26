"""
realocacao.py — Realocação de campanhas de contingência entre contas.

Cenário que isso resolve:
    O orçamento de um cliente acaba no meio da semana e as campanhas são
    recriadas dentro da conta de outro cliente para não parar a entrega.
    No relatório, esses dados voltam para o cliente de origem, somados às
    campanhas originais, e desaparecem do relatório da conta que só
    emprestou o orçamento.

Duas convenções obrigatórias no nome da campanha de contingência:
    1. Manter o mesmo código inicial entre colchetes da campanha original.
       Ex.: [12][MSG ADV+][EASYLIPO][23.07.26] - contingência
            pareia com [12][MSG ADV+][EASYLIPO][18.02.26]
    2. Terminar com o sufixo "- contingência".

Bloco novo no config/contas.json:
    "realocacoes": [
      {
        "origem_slug": "tiago",
        "destino_slug": "clay",
        "sufixo": "- contingência",
        "ativo": true
      }
    ]

Nada aqui chama a API. As funções recebem as listas já coletadas pelo
dados_relatorio_semanal.py e devolvem listas ajustadas.
"""

import re
import unicodedata

SUFIXO_PADRAO = "- contingência"

# Chaves numéricas somáveis. Só entra no cálculo a chave que existir no dict.
CHAVES_SOMA = ("gasto", "resultados", "impressoes", "cliques", "alcance")


# ---------------------------------------------------------------- utilitários

def _norm(txt):
    """Minúsculas, sem acento, sem espaço nas pontas."""
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.strip().lower()


def eh_contingencia(nome, sufixo=SUFIXO_PADRAO):
    return _norm(nome).endswith(_norm(sufixo))


def limpar_sufixo(nome, sufixo=SUFIXO_PADRAO):
    """Remove o sufixo de contingência e o hífen solto que sobra."""
    alvo = _norm(sufixo)
    pos = _norm(nome).rfind(alvo)
    if pos == -1:
        return (nome or "").strip()
    return (nome or "")[:pos].strip().rstrip("-").strip()


def codigo(nome):
    """Extrai o código inicial: '[12][MSG ADV+]...' -> '12'. Sem código, None."""
    m = re.match(r"\s*\[\s*(\d+)\s*\]", nome or "")
    return m.group(1) if m else None


# -------------------------------------------------------------------- config

def realocacao_de_origem(cfg, slug):
    """Regra ativa em que essa conta é a que emprestou o orçamento."""
    for r in cfg.get("realocacoes", []):
        if r.get("ativo", True) and r.get("origem_slug") == slug:
            return r
    return None


def realocacao_de_destino(cfg, slug):
    """Regra ativa em que essa conta é a dona real das campanhas."""
    for r in cfg.get("realocacoes", []):
        if r.get("ativo", True) and r.get("destino_slug") == slug:
            return r
    return None


def conta_por_slug(cfg, slug):
    for c in cfg.get("contas", []):
        if c.get("slug", c["nome"].lower().split()[-1]) == slug:
            return c
    return None


# ------------------------------------------------------------------ separação

def separar_contingencia(campanhas, sufixo=SUFIXO_PADRAO, campo="nome"):
    """Divide em (proprias, contingencia) pelo sufixo no nome."""
    proprias, cont = [], []
    for c in campanhas:
        (cont if eh_contingencia(c.get(campo, ""), sufixo) else proprias).append(c)
    return proprias, cont


def mapear_ids(campanhas_destino, campanhas_contingencia, campo_id="id"):
    """
    De/para dos IDs de campanha, usado para reagrupar os criativos.

    Campanha de contingência com par na conta de destino aponta para o ID da
    campanha original. Sem par, aponta para o próprio ID, porque ela vai
    entrar no relatório como linha própria.
    """
    por_codigo = {}
    for c in campanhas_destino:
        cod = codigo(c.get("nome", ""))
        if cod and cod not in por_codigo:
            por_codigo[cod] = c.get(campo_id)

    mapa = {}
    for cont in campanhas_contingencia:
        cid = cont.get(campo_id)
        cod = codigo(cont.get("nome", ""))
        mapa[cid] = por_codigo.get(cod, cid)
    return mapa


# ----------------------------------------------------------------------- soma

def _somar(destino, origem, chaves=CHAVES_SOMA):
    """Soma as métricas de origem em destino, in place, e recalcula derivadas."""
    for k in chaves:
        if k in destino or k in origem:
            destino[k] = (destino.get(k) or 0) + (origem.get(k) or 0)

    gasto = destino.get("gasto") or 0
    res = destino.get("resultados") or 0
    imp = destino.get("impressoes") or 0

    if "gasto" in destino:
        destino["gasto"] = round(gasto, 2)
    if "cpr" in destino or "cpr" in origem:
        destino["cpr"] = round(gasto / res, 2) if res else None
    if "ctr" in destino or "ctr" in origem:
        destino["ctr"] = ((destino.get("cliques") or 0) / imp * 100) if imp else 0.0
    if "cpm" in destino or "cpm" in origem:
        destino["cpm"] = round(gasto / imp * 1000, 2) if imp else None
    if "frequencia" in destino:
        alc = destino.get("alcance") or 0
        destino["frequencia"] = round(imp / alc, 2) if alc else None

    return destino


def mesclar_campanhas(campanhas_destino, campanhas_contingencia,
                      sufixo=SUFIXO_PADRAO, chaves_soma=CHAVES_SOMA):
    """
    Soma cada campanha de contingência na campanha de mesmo código na conta
    de destino. Sem par, entra como linha nova já com o sufixo removido.
    """
    por_codigo = {}
    for c in campanhas_destino:
        cod = codigo(c.get("nome", ""))
        if cod and cod not in por_codigo:
            por_codigo[cod] = c

    orfas = []
    for cont in campanhas_contingencia:
        cod = codigo(cont.get("nome", ""))
        alvo = por_codigo.get(cod) if cod else None
        if alvo is not None:
            _somar(alvo, cont, chaves_soma)
            alvo.setdefault("_realocado_de", []).append(cont.get("nome"))
        else:
            nova = dict(cont)
            nova["nome"] = limpar_sufixo(nova.get("nome", ""), sufixo)
            nova["_realocado_de"] = [cont.get("nome")]
            orfas.append(nova)

    return campanhas_destino + orfas


def realocar_criativos(criativos_destino, criativos_contingencia, mapa_ids,
                       campo_id="campaign_id", campo_nome="nome",
                       chaves_soma=CHAVES_SOMA):
    """
    Reagrupa os criativos da contingência sob o ID da campanha de destino.

    Criativo com o mesmo nome na mesma campanha é somado ao já existente,
    mantendo o ad_id da conta de destino para a prévia apontar certo.
    Criativo que só rodou na contingência entra como item novo.

    Recebe as listas ainda brutas, antes do corte de top 3.
    """
    indice = {}
    for a in criativos_destino:
        indice.setdefault((a.get(campo_id), _norm(a.get(campo_nome))), a)

    novos = []
    for cont in criativos_contingencia:
        item = dict(cont)
        item[campo_id] = mapa_ids.get(cont.get(campo_id), cont.get(campo_id))
        chave = (item[campo_id], _norm(item.get(campo_nome)))
        alvo = indice.get(chave)
        if alvo is not None:
            _somar(alvo, item, chaves_soma)
            alvo.setdefault("_realocado_de", []).append(cont.get("ad_id"))
        else:
            item["_realocado"] = True
            novos.append(item)
            indice[chave] = item

    return criativos_destino + novos
