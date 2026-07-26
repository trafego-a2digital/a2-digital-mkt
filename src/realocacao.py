"""
realocacao.py — Realocação de campanhas de contingência entre contas.

Cenário que isso resolve:
    O orçamento de um cliente acaba no meio da semana e as campanhas são
    recriadas dentro da conta de outro cliente para não parar a entrega.
    No relatório, esses dados precisam voltar para o cliente de origem,
    somados às campanhas originais, e desaparecer do relatório da conta
    que só emprestou o orçamento.

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


def realocacao_de_origem(cfg, slug_origem):
    """Regra ativa em que a conta informada é a que emprestou o orçamento."""
    for r in cfg.get("realocacoes", []):
        if r.get("ativo", True) and r.get("origem_slug") == slug_origem:
            return r
    return None


def realocacao_de_destino(cfg, slug_destino):
    """Regra ativa em que a conta informada é a dona real das campanhas."""
    for r in cfg.get("realocacoes", []):
        if r.get("ativo", True) and r.get("destino_slug") == slug_destino:
            return r
    return None


def conta_por_slug(cfg, slug):
    for c in cfg.get("contas", []):
        if c.get("slug") == slug:
            return c
    return None


# ------------------------------------------------------------------- separação

def separar_contingencia(itens, sufixo=SUFIXO_PADRAO, campo="nome"):
    """
    Divide em (proprias, contingencia) pelo sufixo no campo informado.

    Uso na conta de origem (Tiago), nível campanha:
        proprias, _ = separar_contingencia(campanhas)
    Uso no nível anúncio, olhando o nome da campanha do anúncio:
        proprios, _ = separar_contingencia(anuncios, campo="campanha")
    """
    proprias, cont = [], []
    for i in itens:
        destino = cont if eh_contingencia(i.get(campo, ""), sufixo) else proprias
        destino.append(i)
    return proprias, cont


# ----------------------------------------------------------------------- soma

def _somar(destino, origem, chaves=CHAVES_SOMA):
    """Soma as métricas de origem em destino, in place, e recalcula derivadas."""
    for k in chaves:
        if k in destino or k in origem:
            destino[k] = (destino.get(k) or 0) + (origem.get(k) or 0)

    gasto = destino.get("gasto") or 0
    res = destino.get("resultados") or 0
    if "cpr" in destino or "cpr" in origem:
        destino["cpr"] = (gasto / res) if res else None

    imp = destino.get("impressoes") or 0
    if "ctr" in destino or "ctr" in origem:
        destino["ctr"] = ((destino.get("cliques") or 0) / imp * 100) if imp else None
    if "cpm" in destino or "cpm" in origem:
        destino["cpm"] = (gasto / imp * 1000) if imp else None

    # Frequência não é somável nem reconstruível sem alcance real da soma.
    if "frequencia" in destino and "alcance" in destino and imp:
        alc = destino.get("alcance") or 0
        destino["frequencia"] = (imp / alc) if alc else None

    return destino


def mesclar_campanhas(campanhas_destino, campanhas_contingencia,
                      sufixo=SUFIXO_PADRAO, chaves_soma=CHAVES_SOMA):
    """
    Soma cada campanha de contingência na campanha de mesmo código na conta
    de destino. Sem par, entra como linha nova já com o sufixo removido.

    Devolve a lista pronta para a montagem do HTML e do JSON.
    """
    indice = {}
    for c in campanhas_destino:
        cod = codigo(c.get("nome", ""))
        if cod and cod not in indice:
            indice[cod] = c

    orfas = []
    for cont in campanhas_contingencia:
        cod = codigo(cont.get("nome", ""))
        alvo = indice.get(cod) if cod else None
        if alvo is not None:
            _somar(alvo, cont, chaves_soma)
            alvo.setdefault("_realocado_de", []).append(cont.get("nome"))
        else:
            nova = dict(cont)
            nova["nome"] = limpar_sufixo(nova.get("nome", ""), sufixo)
            nova["_realocado_de"] = [cont.get("nome")]
            orfas.append(nova)

    return campanhas_destino + orfas


def mesclar_anuncios(anuncios_destino, anuncios_contingencia,
                     sufixo=SUFIXO_PADRAO, chaves_soma=CHAVES_SOMA,
                     campo_campanha="campanha", campo_nome="nome"):
    """
    Mesma lógica no nível anúncio, para o top 3 de criativos sair correto.

    O pareamento é pelo par (código da campanha, nome do criativo). Criativo
    que só rodou na contingência entra como linha nova, com o nome da campanha
    já ajustado pelo código correspondente na conta de destino.
    """
    nome_por_codigo = {}
    for a in anuncios_destino:
        cod = codigo(a.get(campo_campanha, ""))
        if cod and cod not in nome_por_codigo:
            nome_por_codigo[cod] = a.get(campo_campanha)

    indice = {}
    for a in anuncios_destino:
        chave = (codigo(a.get(campo_campanha, "")), _norm(a.get(campo_nome)))
        indice.setdefault(chave, a)

    novos = []
    for cont in anuncios_contingencia:
        cod = codigo(cont.get(campo_campanha, ""))
        chave = (cod, _norm(cont.get(campo_nome)))
        alvo = indice.get(chave)
        if alvo is not None:
            _somar(alvo, cont, chaves_soma)
            alvo.setdefault("_realocado_de", []).append(cont.get(campo_nome))
        else:
            novo = dict(cont)
            novo[campo_campanha] = nome_por_codigo.get(
                cod, limpar_sufixo(novo.get(campo_campanha, ""), sufixo))
            novo["_realocado_de"] = [cont.get(campo_nome)]
            novos.append(novo)

    return anuncios_destino + novos
