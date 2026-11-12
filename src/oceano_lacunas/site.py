"""Bloco `para_o_site`: os textos trilíngues e a especificação do gráfico interativo do portfólio.

Todo número sai do dicionário de resultados; as frases que dependem do desfecho da validação são
escolhidas pelo intervalo de confiança, não fixadas à mão.
"""

from __future__ import annotations

from . import dados


def _num(valor: float, casas: int, idioma: str) -> str:
    texto = f"{valor:.{casas}f}"
    return texto if idioma == "en" else texto.replace(".", ",")


def _pct(valor: float, idioma: str) -> str:
    return f"{round(valor * 100)}%"


def _comparacao(base: dict, rho_base: dict) -> dict[str, str]:
    """Frase sobre a linha de base 'menos registros', conforme o intervalo da diferença."""
    b = {i: _num(base["spearman"], 2, i) for i in ("pt", "en", "es")}
    if base["vantagem_inf"] > 0:
        return {
            "pt": f"acima da regra simples de ir aonde há menos registros ({b['pt']})",
            "en": f"clearly better than the simple rule of going where records are fewest ({b['en']})",
            "es": f"por encima de la regla simple de ir adonde hay menos registros ({b['es']})",
        }
    if base["vantagem_do_retorno_chao1"] > 0:
        return {
            "pt": f"contra {b['pt']} da regra simples de ir aonde há menos registros, uma diferença que cabe no acaso",
            "en": f"versus {b['en']} for the simple rule of going where records are fewest, a gap that chance alone could produce",
            "es": f"frente a {b['es']} de la regla simple de ir adonde hay menos registros, una diferencia que cabe en el azar",
        }
    return {
        "pt": f"e a regra simples de ir aonde há menos registros fez igual ou melhor ({b['pt']})",
        "en": f"and the simple rule of going where records are fewest did as well or better ({b['en']})",
        "es": f"y la regla simple de ir adonde hay menos registros lo hizo igual o mejor ({b['es']})",
    }


def _conta_simples(gt: dict) -> dict[str, str]:
    """Frase sobre a conta de uma linha (singletons por registro), conforme o intervalo da diferença."""
    g = {i: _num(gt["spearman"], 2, i) for i in ("pt", "en", "es")}
    if gt["vantagem_inf"] <= 0 <= gt["vantagem_sup"]:
        return {
            "pt": f"mas empatado com a conta de uma linha, singletons por registro ({g['pt']})",
            "en": f"but tied with the one-line rule, singletons per record ({g['en']})",
            "es": f"pero empatado con la cuenta de una línea, singletons por registro ({g['es']})",
        }
    if gt["vantagem_inf"] > 0:
        return {
            "pt": f"e acima da conta de uma linha, singletons por registro ({g['pt']})",
            "en": f"and better than the one-line rule, singletons per record ({g['en']})",
            "es": f"y por encima de la cuenta de una línea, singletons por registro ({g['es']})",
        }
    return {
        "pt": f"mas abaixo da conta de uma linha, singletons por registro ({g['pt']})",
        "en": f"but worse than the one-line rule, singletons per record ({g['en']})",
        "es": f"pero por debajo de la cuenta de una línea, singletons por registro ({g['es']})",
    }


def bloco(r: dict) -> dict:
    esforco, validacao = r["esforco"], r["validacao"]
    faixas = esforco["por_faixa"]
    unidades = sum(f["unidades"] for f in faixas.values())
    sem_dado = sum(f["unidades_sem_registro"] + f["unidades_insuficientes"] for f in faixas.values()) / unidades
    fundo = faixas["4000+"]["fracao_da_area_sem_registro"]
    metodo = validacao["regras"]["retorno (Chao1)"]
    base = validacao["regras"]["menos registros"]
    razao = validacao["calibracao_por_mil"]["razao_mediana_realizado_previsto"]
    obis = esforco["obis_inteiro"]
    milhoes, mil_especies = obis["registros"] / 1e6, obis["especies"] / 1e3
    dia = r["coleta"]["coletado_em"][:10]
    data = {"pt": f"{dia[8:10]}/{dia[5:7]}/{dia[:4]}", "es": f"{dia[8:10]}/{dia[5:7]}/{dia[:4]}", "en": dia}
    corte = validacao["ano_de_corte"]
    comp = _comparacao(base, metodo)
    simples = _conta_simples(validacao["regras"]["retorno (Good-Turing)"])
    comp = {i: f"{comp[i]}, {simples[i]}" for i in comp}
    rho = {i: _num(metodo["spearman"], 2, i) for i in ("pt", "en", "es")}
    vezes = {i: _num(razao, 1, i) for i in ("pt", "en", "es")}

    rotulos = {
        "pt": ["0 a 200 m", "200 a 1.000 m", "1.000 a 4.000 m", "mais de 4.000 m"],
        "en": ["0–200 m", "200–1,000 m", "1,000–4,000 m", "below 4,000 m"],
        "es": ["0 a 200 m", "200 a 1.000 m", "1.000 a 4.000 m", "más de 4.000 m"],
    }
    sem_inventario = [[rotulos["pt"][i], round(faixas[f]["fracao_da_area_sem_inventario"], 4)] for i, f in enumerate(dados.ID_FAIXAS)]
    sem_registro = [[rotulos["pt"][i], round(faixas[f]["fracao_da_area_sem_registro"], 4)] for i, f in enumerate(dados.ID_FAIXAS)]

    return {
        "numero_chave": {"pt": f"{_pct(sem_dado, 'pt')} sem dado", "en": f"{_pct(sem_dado, 'en')} no data", "es": f"{_pct(sem_dado, 'es')} sin dato"},
        "pergunta": {
            "pt": "Onde o oceano ainda não foi amostrado, e onde uma expedição renderia mais espécies ainda não registradas?",
            "en": "Where has the ocean not been sampled yet, and where would an expedition add the most species not yet on record?",
            "es": "¿Dónde no se ha muestreado todavía el océano, y dónde una expedición sumaría más especies aún sin registrar?",
        },
        "resultado": {
            "pt": (
                f"Em {_pct(sem_dado, 'pt')} das combinações de célula de 10° e faixa de profundidade, o OBIS não tem registros "
                f"suficientes nem para estimar quantas espécies faltam; abaixo de 4.000 m, {_pct(fundo, 'pt')} da área não tem um "
                f"registro sequer. Onde há dado, ordenar as células pelo retorno esperado teve correlação de {rho['pt']} com as "
                f"espécies novas que de fato apareceram depois de {corte}, {comp['pt']}."
            ),
            "en": (
                f"In {_pct(sem_dado, 'en')} of all combinations of 10° cell and depth band, OBIS holds too few records to even "
                f"estimate how many species are missing; below 4,000 m, {_pct(fundo, 'en')} of the area has no record at all. Where "
                f"data exist, ranking cells by expected return correlated {rho['en']} with the new species that actually turned up "
                f"after {corte}, {comp['en']}."
            ),
            "es": (
                f"En el {_pct(sem_dado, 'es')} de las combinaciones de celda de 10° y franja de profundidad, OBIS no tiene registros "
                f"suficientes ni para estimar cuántas especies faltan; por debajo de 4.000 m, el {_pct(fundo, 'es')} del área no "
                f"tiene un solo registro. Donde hay datos, ordenar las celdas por retorno esperado tuvo una correlación de "
                f"{rho['es']} con las especies nuevas que de verdad aparecieron después de {corte}, {comp['es']}."
            ),
        },
        "detalhe": {
            "pt": (
                "O gráfico mostra, por faixa de profundidade, a fração da área de oceano sem os 500 registros de espécie de que os "
                "estimadores precisam e, dentro dela, a fração sem nenhum registro. A previsão acerta melhor a ordem do que o "
                f"tamanho: depois de {corte} apareceram {vezes['pt']} vezes mais espécies novas por mil registros do que o previsto, "
                "e “nova” aqui é nova para a célula no OBIS, não para a ciência."
            ),
            "en": (
                "The chart shows, for each depth band, the share of ocean area lacking the 500 species-level records the estimators "
                "need and, within it, the share with no record at all. The forecast gets the order better than the size: after "
                f"{corte}, {vezes['en']} times more new species per thousand records turned up than predicted, and “new” here "
                "means new to the cell in OBIS, not new to science."
            ),
            "es": (
                "El gráfico muestra, por franja de profundidad, la fracción del área oceánica sin los 500 registros de especie que "
                "necesitan los estimadores y, dentro de ella, la fracción sin ningún registro. La previsión acierta mejor el orden "
                f"que el tamaño: después de {corte} aparecieron {vezes['es']} veces más especies nuevas por mil registros de lo "
                "previsto, y “nueva” aquí es nueva para la celda en OBIS, no para la ciencia."
            ),
        },
        "dados": {
            "pt": f"OBIS, {_num(milhoes, 0, 'pt')} milhões de registros e {_num(mil_especies, 0, 'pt')} mil espécies, agregados numa grade global de 10° x 10° em quatro faixas de profundidade; coleta de {data['pt']}.",
            "en": f"OBIS, {_num(milhoes, 0, 'en')} million records and {_num(mil_especies, 0, 'en')} thousand species, aggregated on a global 10° x 10° grid in four depth bands; retrieved {data['en']}.",
            "es": f"OBIS, {_num(milhoes, 0, 'es')} millones de registros y {_num(mil_especies, 0, 'es')} mil especies, agregados en una cuadrícula global de 10° x 10° en cuatro franjas de profundidad; consulta del {data['es']}.",
        },
        "etiquetas": ["biodiversidade marinha", "estimadores de riqueza", "Chao1", "esforço de amostragem", "validação no tempo", "OBIS"],
        "grafico": {
            "tipo": "barras",
            "titulo": {
                "pt": "Quanto do oceano não tem dado nem para estimar, por profundidade",
                "en": "How much of the ocean lacks the data to even estimate, by depth",
                "es": "Cuánto del océano no tiene datos ni para estimar, por profundidad",
            },
            "eixo_x": {"pt": "Faixa de profundidade", "en": "Depth band", "es": "Franja de profundidad"},
            "eixo_y": {"pt": "Fração da área de oceano", "en": "Share of ocean area", "es": "Fracción del área oceánica"},
            "formato_x": "numero",
            "formato_y": "percentual",
            "rotulos": rotulos,
            "series": [
                {
                    "nome": {
                        "pt": "Sem registros suficientes para estimar (menos de 500 de espécie)",
                        "en": "Too few records to estimate (under 500 at species level)",
                        "es": "Sin registros suficientes para estimar (menos de 500 de especie)",
                    },
                    "papel": "principal",
                    "pontos": sem_inventario,
                    "rotulos": rotulos,
                },
                {
                    "nome": {"pt": "Sem nenhum registro", "en": "No record at all", "es": "Sin ningún registro"},
                    "papel": "base",
                    "pontos": sem_registro,
                    "rotulos": rotulos,
                },
            ],
        },
    }
