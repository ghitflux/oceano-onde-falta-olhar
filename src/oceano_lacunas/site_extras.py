"""Gráficos adicionais do bloco `para_o_site`, como dados, para o site desenhar nativamente.

Cada especificação equivale a uma figura do README que não está no gráfico principal. Os mapas não
entram (o site não desenha mapa): o mapa do esforço vira barras por faixa de profundidade e
hemisfério, e o mapa de prioridades já está resumido no gráfico principal. Todo valor sai do
dicionário de resultados; os títulos que dependem do desfecho são escolhidos pelo intervalo.
"""

from __future__ import annotations

import numpy as np

from . import dados

IDIOMAS = ("pt", "en", "es")
ROTULOS_FAIXA = {
    "pt": ["0 a 200 m", "200 a 1.000 m", "1.000 a 4.000 m", "mais de 4.000 m"],
    "en": ["0–200 m", "200–1,000 m", "1,000–4,000 m", "below 4,000 m"],
    "es": ["0 a 200 m", "200 a 1.000 m", "1.000 a 4.000 m", "más de 4.000 m"],
}
GRUPOS_DA_CALIBRACAO = 8
COMUNIDADE_DIFICIL = "muitas raras"


def _n(valor: float, casas: int) -> dict[str, str]:
    """O mesmo número nos três idiomas (pt e es com vírgula decimal)."""
    texto = f"{valor:.{casas}f}"
    return {"pt": texto.replace(".", ","), "en": texto, "es": texto.replace(".", ",")}


def _p(valor: float, casas: int = 0) -> dict[str, str]:
    return {i: f"{t}%" for i, t in _n(valor * 100, casas).items()}


def _milhar(valor: float) -> dict[str, str]:
    us = f"{valor:,.0f}"
    return {"pt": us.replace(",", "."), "en": us, "es": us.replace(",", ".")}


def rankings(r: dict) -> dict:
    """Barras: a correlação de cada regra de prioridade com o que apareceu depois do corte."""
    v = r["validacao"]
    regras, corte = v["regras"], v["ano_de_corte"]
    metodo, base, gt = regras["retorno (Chao1)"], regras["menos registros"], regras["retorno (Good-Turing)"]
    a, b = _n(metodo["spearman"], 2), _n(base["spearman"], 2)
    if base["vantagem_inf"] > 0:
        titulo = {
            "pt": f"O retorno esperado ordena melhor que ir aonde há menos registros: {a['pt']} contra {b['pt']}",
            "en": f"Expected return ranks better than going where records are fewest: {a['en']} vs {b['en']}",
            "es": f"El retorno esperado ordena mejor que ir adonde hay menos registros: {a['es']} frente a {b['es']}",
        }
    elif base["vantagem_do_retorno_chao1"] > 0:
        titulo = {
            "pt": f"Retorno esperado e “menos registros” ordenam parecido: {a['pt']} contra {b['pt']}",
            "en": f"Expected return and “fewest records” rank about the same: {a['en']} vs {b['en']}",
            "es": f"Retorno esperado y “menos registros” ordenan parecido: {a['es']} frente a {b['es']}",
        }
    else:
        titulo = {
            "pt": f"Ir aonde há menos registros ordena tão bem quanto o retorno esperado: {b['pt']} e {a['pt']}",
            "en": f"Going where records are fewest ranks as well as expected return: {b['en']} and {a['en']}",
            "es": f"Ir adonde hay menos registros ordena tan bien como el retorno esperado: {b['es']} y {a['es']}",
        }
    empate = gt["vantagem_inf"] <= 0 <= gt["vantagem_sup"]
    final = {
        "pt": " A conta de uma linha (singletons por registro) empata com a extrapolação." if empate else "",
        "en": " The one-line rule (singletons per record) ties with the extrapolation." if empate else "",
        "es": " La cuenta de una línea (singletons por registro) empata con la extrapolación." if empate else "",
    }
    nomes = {
        "retorno (Chao1)": ("Retorno esperado (Chao1)", "Expected return (Chao1)", "Retorno esperado (Chao1)"),
        "retorno (ACE)": ("Retorno esperado (ACE)", "Expected return (ACE)", "Retorno esperado (ACE)"),
        "retorno (Good-Turing)": ("Singletons por registro", "Singletons per record", "Singletons por registro"),
        "menos registros": ("Menos registros", "Fewest records", "Menos registros"),
        "mais espécies registradas": ("Mais espécies registradas", "Most recorded species", "Más especies registradas"),
    }
    ordem = [n for n in nomes if n in regras]
    rotulos = {idioma: [nomes[n][k] for n in ordem] for k, idioma in enumerate(IDIOMAS)}
    return {
        "tipo": "barras",
        "titulo": titulo,
        "leitura": {
            "pt": f"Correlação de postos entre cada regra, aplicada só aos dados até {corte}, e as espécies novas que apareceram depois, em {v['unidades']} unidades.{final['pt']}",
            "en": f"Rank correlation between each rule, applied only to data up to {corte}, and the new species recorded afterwards, across {v['unidades']} units.{final['en']}",
            "es": f"Correlación de rangos entre cada regla, aplicada solo a los datos hasta {corte}, y las especies nuevas que aparecieron después, en {v['unidades']} unidades.{final['es']}",
        },
        "eixo_x": {"pt": "Regra de prioridade", "en": "Priority rule", "es": "Regla de prioridad"},
        "eixo_y": {"pt": "Correlação de Spearman com o realizado", "en": "Spearman correlation with the outcome", "es": "Correlación de Spearman con lo realizado"},
        "formato_x": "numero",
        "formato_y": "numero",
        "series": [
            {
                "nome": {"pt": "Correlação com o realizado", "en": "Correlation with the outcome", "es": "Correlación con lo realizado"},
                "papel": "principal",
                "pontos": [[rotulos["pt"][k], round(regras[n]["spearman"], 3)] for k, n in enumerate(ordem)],
                "rotulos": rotulos,
            }
        ],
    }


def calibracao(r: dict) -> dict:
    """Linhas: previsto contra realizado, com as unidades agrupadas em faixas do previsto.

    A figura do README é uma dispersão em escala log; aqui as unidades são ordenadas pelo previsto e
    divididas em grupos de tamanho igual, e cada ponto é a mediana do grupo, com a faixa entre o 1º e
    o 3º quartil do realizado. A série de base é a diagonal previsto = realizado.
    """
    v = r["validacao"]
    unidades = sorted(r["validacao_por_unidade"], key=lambda u: u["previsto"])
    grupos = np.array_split(np.arange(len(unidades)), min(GRUPOS_DA_CALIBRACAO, len(unidades)))
    mediana, inferior, superior, diagonal = [], [], [], []
    for grupo in grupos:
        x = float(np.median([unidades[i]["previsto"] for i in grupo]))
        y = np.array([unidades[i]["realizado"] for i in grupo])
        mediana.append([round(x, 2), round(float(np.median(y)), 2)])
        inferior.append([round(x, 2), round(float(np.quantile(y, 0.25)), 2)])
        superior.append([round(x, 2), round(float(np.quantile(y, 0.75)), 2)])
        diagonal.append([round(x, 2), round(x, 2)])
    vezes = _n(v["calibracao_por_mil"]["razao_mediana_realizado_previsto"], 1)
    dentro = _p(v["calibracao_por_mil"]["fracao_dentro_do_intervalo"])
    corte = v["ano_de_corte"]
    if v["regras"]["retorno (Chao1)"]["spearman_inf"] > 0:
        titulo = {
            "pt": f"A ordem se aproveita, o tamanho não: apareceu {vezes['pt']} vezes o previsto",
            "en": f"The order holds, the size does not: {vezes['en']} times the forecast turned up",
            "es": f"El orden se aprovecha, el tamaño no: apareció {vezes['es']} veces lo previsto",
        }
    else:
        titulo = {
            "pt": f"Nem a ordem nem o tamanho se confirmam: apareceu {vezes['pt']} vezes o previsto",
            "en": f"Neither order nor size holds: {vezes['en']} times the forecast turned up",
            "es": f"Ni el orden ni el tamaño se confirman: apareció {vezes['es']} veces lo previsto",
        }
    return {
        "tipo": "linhas",
        "titulo": titulo,
        "leitura": {
            "pt": f"Unidades agrupadas pelo previsto com dados até {corte}; cada ponto é a mediana do grupo e a faixa vai do 1º ao 3º quartil do realizado. Só {dentro['pt']} dos realizados caíram no intervalo de 95% da previsão.",
            "en": f"Units grouped by the forecast made with data up to {corte}; each point is the group median and the band spans the interquartile range of the outcome. Only {dentro['en']} of outcomes fell inside the forecast's 95% interval.",
            "es": f"Unidades agrupadas por lo previsto con datos hasta {corte}; cada punto es la mediana del grupo y la franja va del 1.º al 3.º cuartil de lo realizado. Solo el {dentro['es']} de lo realizado cayó en el intervalo del 95% de la previsión.",
        },
        "eixo_x": {
            "pt": "Previsto: espécies novas por mil registros",
            "en": "Forecast: new species per thousand records",
            "es": "Previsto: especies nuevas por mil registros",
        },
        "eixo_y": {
            "pt": "Realizado: espécies novas em mil registros posteriores",
            "en": "Outcome: new species in a thousand later records",
            "es": "Realizado: especies nuevas en mil registros posteriores",
        },
        "formato_x": "numero",
        "formato_y": "numero",
        "series": [
            {"nome": {"pt": "Realizado (mediana do grupo)", "en": "Outcome (group median)", "es": "Realizado (mediana del grupo)"}, "papel": "principal", "pontos": mediana},
            {"nome": {"pt": "Previsto = realizado", "en": "Forecast = outcome", "es": "Previsto = realizado"}, "papel": "base", "pontos": diagonal},
        ],
        "faixa": {"serie": 0, "inferior": inferior, "superior": superior},
    }


def _reduzir(curva: list[list[float]]) -> list[list[float]]:
    """Reduz a curva de Lorenz a no máximo 80 pontos sem perder a ponta, onde ela sobe de uma vez:
    um ponto a cada 2% da área até 90% e todos dali em diante."""
    return [[round(x, 4), round(y, 4)] for i, (x, y) in enumerate(curva) if x >= 0.9 or i % 2 == 0][:80]


def lorenz(r: dict) -> dict:
    """Linhas: curva de Lorenz do esforço (todos os registros e a faixa mais funda) e a diagonal."""
    d = r["esforco"]["desigualdade_celulas"]
    curvas = r["curvas_de_lorenz"]
    metade = _p(d["fracao_da_area_com_metade_dos_registros"], 1)
    pobre = _p(d["fracao_dos_registros_na_metade_menos_amostrada"], 1)
    gini = _n(d["gini"], 2)
    todas = _reduzir(curvas["todas"])
    return {
        "tipo": "linhas",
        "titulo": {
            "pt": f"Metade dos registros do OBIS vem de {metade['pt']} da área do oceano",
            "en": f"Half of all OBIS records come from {metade['en']} of the ocean's area",
            "es": f"La mitad de los registros de OBIS viene del {metade['es']} del área del océano",
        },
        "leitura": {
            "pt": f"Curva de Lorenz: células de 10° x 10° da menos para a mais amostrada. A metade menos amostrada do oceano guarda {pobre['pt']} dos registros (Gini de {gini['pt']}); com esforço uniforme a curva seguiria a diagonal.",
            "en": f"Lorenz curve: 10° x 10° cells from least to most sampled. The less-sampled half of the ocean holds {pobre['en']} of the records (Gini {gini['en']}); uniform effort would follow the diagonal.",
            "es": f"Curva de Lorenz: celdas de 10° x 10° de la menos a la más muestreada. La mitad menos muestreada del océano guarda el {pobre['es']} de los registros (Gini de {gini['es']}); con esfuerzo uniforme la curva seguiría la diagonal.",
        },
        "eixo_x": {"pt": "Fração acumulada da área de oceano", "en": "Cumulative share of ocean area", "es": "Fracción acumulada del área oceánica"},
        "eixo_y": {"pt": "Fração acumulada dos registros", "en": "Cumulative share of records", "es": "Fracción acumulada de los registros"},
        "formato_x": "percentual",
        "formato_y": "percentual",
        "series": [
            {"nome": {"pt": "Todos os registros", "en": "All records", "es": "Todos los registros"}, "papel": "principal", "pontos": todas},
            {
                "nome": {"pt": "Registros abaixo de 4.000 m", "en": "Records below 4,000 m", "es": "Registros por debajo de 4.000 m"},
                "papel": "alternativa",
                "pontos": _reduzir(curvas["4000+"]),
            },
            {"nome": {"pt": "Esforço uniforme", "en": "Uniform effort", "es": "Esfuerzo uniforme"}, "papel": "base", "pontos": [[x, x] for x, _ in todas]},
        ],
    }


def esforco_por_faixa(r: dict) -> dict:
    """Barras no lugar do mapa do esforço: registros por mil km² por faixa de profundidade e hemisfério."""
    e = r["esforco"]
    queda = _milhar(e["razao_superficie_fundo"])
    norte_sul = _n(e["razao_norte_sul_superficie"], 1)
    raso, fundo = e["por_faixa"]["0-200"]["registros_por_mil_km2"], e["por_faixa"]["4000+"]["registros_por_mil_km2"]
    a, b = _milhar(raso), _n(fundo, 1)

    def serie(hemisferio: str) -> list[list]:
        return [[ROTULOS_FAIXA["pt"][k], round(e["por_hemisferio"][hemisferio][f], 2)] for k, f in enumerate(dados.ID_FAIXAS)]

    return {
        "tipo": "barras",
        "titulo": {
            "pt": f"O esforço cai {queda['pt']} vezes da superfície ao fundo; o norte tem {norte_sul['pt']} vezes o do sul",
            "en": f"Effort drops {queda['en']}-fold from surface to deep sea; the north has {norte_sul['en']} times the south's",
            "es": f"El esfuerzo cae {queda['es']} veces de la superficie al fondo; el norte tiene {norte_sul['es']} veces el del sur",
        },
        "leitura": {
            "pt": f"Registros com profundidade informada por mil km² de oceano: {a['pt']} de 0 a 200 m contra {b['pt']} abaixo de 4.000 m. A razão entre hemisférios é a da faixa de 0 a 200 m.",
            "en": f"Records with a stated depth per thousand km² of ocean: {a['en']} at 0–200 m versus {b['en']} below 4,000 m. The hemisphere ratio is for the 0–200 m band.",
            "es": f"Registros con profundidad informada por mil km² de océano: {a['es']} de 0 a 200 m frente a {b['es']} por debajo de 4.000 m. La razón entre hemisferios es la de la franja de 0 a 200 m.",
        },
        "eixo_x": {"pt": "Faixa de profundidade", "en": "Depth band", "es": "Franja de profundidad"},
        "eixo_y": {"pt": "Registros por mil km² de oceano", "en": "Records per thousand km² of ocean", "es": "Registros por mil km² de océano"},
        "formato_x": "numero",
        "formato_y": "numero",
        "series": [
            {"nome": {"pt": "Hemisfério norte", "en": "Northern hemisphere", "es": "Hemisferio norte"}, "papel": "principal", "pontos": serie("Norte"), "rotulos": ROTULOS_FAIXA},
            {"nome": {"pt": "Hemisfério sul", "en": "Southern hemisphere", "es": "Hemisferio sur"}, "papel": "alternativa", "pontos": serie("Sul"), "rotulos": ROTULOS_FAIXA},
        ],
    }


def simulacao(r: dict) -> dict:
    """Barras: na comunidade simulada com muitas espécies raras, quanto da riqueza verdadeira cada
    conta enxerga por tamanho de amostra, e quanto a previsão de curto prazo acerta."""
    linhas = [s for s in r["simulacao"] if s["comunidade"] == COMUNIDADE_DIFICIL]
    tamanhos = [_milhar(s["registros"]) for s in linhas]
    rotulos = {i: [t[i] for t in tamanhos] for i in IDIOMAS}
    menor, maior = linhas[0], linhas[-1]
    pouco, muito = _p(menor["chao1_sobre_real"]), _p(maior["chao1_sobre_real"])
    n_menor, n_maior = _milhar(menor["registros"]), _milhar(maior["registros"])

    def serie(coluna: str) -> list[list]:
        return [[rotulos["pt"][k], round(s[coluna], 4)] for k, s in enumerate(linhas)]

    return {
        "tipo": "barras",
        "titulo": {
            "pt": f"Com {n_menor['pt']} registros o Chao1 vê {pouco['pt']} da riqueza real; com {n_maior['pt']}, {muito['pt']}",
            "en": f"With {n_menor['en']} records Chao1 sees {pouco['en']} of true richness; with {n_maior['en']}, {muito['en']}",
            "es": f"Con {n_menor['es']} registros el Chao1 ve el {pouco['es']} de la riqueza real; con {n_maior['es']}, el {muito['es']}",
        },
        "leitura": {
            "pt": "Comunidade simulada com 2.000 espécies, muitas delas raras. A riqueza total é sempre subestimada, mas a previsão de espécies novas nos próximos mil registros fica perto de 100% do valor verdadeiro a partir de mil registros.",
            "en": "Simulated community of 2,000 species, many of them rare. Total richness is always underestimated, yet the forecast of new species in the next thousand records stays close to 100% of the true value from a thousand records on.",
            "es": "Comunidad simulada con 2.000 especies, muchas de ellas raras. La riqueza total siempre se subestima, pero la previsión de especies nuevas en los próximos mil registros queda cerca del 100% del valor verdadero a partir de mil registros.",
        },
        "eixo_x": {"pt": "Registros na amostra", "en": "Records in the sample", "es": "Registros en la muestra"},
        "eixo_y": {"pt": "Estimativa sobre o valor verdadeiro", "en": "Estimate over the true value", "es": "Estimación sobre el valor verdadero"},
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            {"nome": {"pt": "Chao1 sobre a riqueza real", "en": "Chao1 over true richness", "es": "Chao1 sobre la riqueza real"}, "papel": "principal", "pontos": serie("chao1_sobre_real"), "rotulos": rotulos},
            {"nome": {"pt": "Espécies observadas sobre a riqueza real", "en": "Observed species over true richness", "es": "Especies observadas sobre la riqueza real"}, "papel": "base", "pontos": serie("observada_sobre_real"), "rotulos": rotulos},
            {
                "nome": {
                    "pt": "Previsão de curto prazo sobre o valor verdadeiro",
                    "en": "Short-term forecast over the true value",
                    "es": "Previsión de corto plazo sobre el valor verdadero",
                },
                "papel": "alternativa",
                "pontos": serie("previstas_sobre_verdadeiras"),
                "rotulos": rotulos,
            },
        ],
    }


def graficos(r: dict) -> list[dict]:
    """As cinco especificações, do achado mais importante para o menos."""
    return [rankings(r), calibracao(r), esforco_por_faixa(r), lorenz(r), simulacao(r)]
