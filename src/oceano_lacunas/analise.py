"""Orquestra cada tabela do estudo. Cada número do README sai de uma função daqui."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from . import dados, esforco, riqueza

SEMENTE = 20261112
MIN_REGISTROS = 500  # registros identificados até espécie para a unidade ser "avaliável"
EXTRA = 1000  # a pergunta de decisão: espécies novas nos próximos mil registros
REPETICOES = 200  # réplicas de bootstrap por unidade
AREA_MINIMA_KM2 = 20_000  # abaixo disso a faixa de profundidade quase não existe na célula
MIN_POSTERIORES = 1000  # registros depois do corte para a unidade entrar na validação
TOPO = 20  # tamanho da lista curta de prioridades
DOMINANCIA_ALTA = 0.5

ZONAS = ["sem registro", "amostra insuficiente", "avaliável"]


# ----------------------------------------------------------------------------------------------
# Unidades
# ----------------------------------------------------------------------------------------------


def montar_unidades(celulas: pd.DataFrame, unidades: pd.DataFrame) -> pd.DataFrame:
    """Todas as combinações de célula e faixa em que há água ou registro, com a zona de cada uma.

    - "sem registro": a faixa existe na célula (área de água acima do mínimo) e não há registro.
    - "amostra insuficiente": há registro, mas menos de `MIN_REGISTROS` identificados até espécie.
      Extrapolar mil registros a partir de menos de 500 passa do dobro da amostra, e os estimadores
      deixam de ser confiáveis.
    - "avaliável": o resto.
    """
    grade = celulas.melt(
        id_vars=["celula", "lat_sul", "lon_oeste", "fracao_oceano"],
        value_vars=[f"area_{f}_km2" for f in dados.ID_FAIXAS],
        var_name="faixa",
        value_name="area_faixa_km2",
    )
    grade["faixa"] = grade["faixa"].str.removeprefix("area_").str.removesuffix("_km2")
    tabela = grade.merge(unidades, on=["celula", "faixa"], how="left")
    for coluna in ("registros", "registros_especie", "registros_genero", "especies"):
        tabela[coluna] = tabela[coluna].fillna(0).astype(int)
    tabela["tem_agua"] = tabela["area_faixa_km2"] >= AREA_MINIMA_KM2
    tabela = tabela[tabela["tem_agua"] | (tabela["registros"] > 0)].reset_index(drop=True)
    tabela["hemisferio"] = np.where(tabela["lat_sul"] >= 0, "Norte", "Sul")
    tabela["rotulo"] = [dados.rotulo_celula(a, o) for a, o in zip(tabela["lat_sul"], tabela["lon_oeste"])]
    tabela["densidade"] = np.where(tabela["tem_agua"], tabela["registros"] / tabela["area_faixa_km2"] * 1000, np.nan)
    tabela["zona"] = np.select(
        [tabela["registros"] == 0, tabela["registros_especie"] < MIN_REGISTROS], ZONAS[:2], default=ZONAS[2]
    )
    return tabela


# ----------------------------------------------------------------------------------------------
# 1. Esforço
# ----------------------------------------------------------------------------------------------


def resumo_do_esforco(unid: pd.DataFrame, celulas: pd.DataFrame, coleta: dict) -> dict:
    """Totais, densidade por faixa e hemisfério, desigualdade (Gini) e registros sem profundidade."""
    globais = coleta["globais"]
    com_agua = unid[unid["tem_agua"]]
    total_unidades = int(unid["registros"].sum())
    saida: dict = {
        "obis_inteiro": {
            "registros": globais["geral"]["records"],
            "especies": globais["geral"]["species"],
            "conjuntos": globais["geral"]["datasets"],
            "registros_com_profundidade": globais["com_profundidade"]["records"],
            "fracao_sem_profundidade": 1 - globais["com_profundidade"]["records"] / globais["geral"]["records"],
            "fracao_identificada_ate_especie": globais["geral"]["specieslevel"] / globais["geral"]["records"],
            "registros_ate_corte": globais["ate_corte"]["records"],
            "registros_depois_corte": globais["depois_corte"]["records"],
            "fracao_sem_data": 1
            - (globais["ate_corte"]["records"] + globais["depois_corte"]["records"]) / globais["geral"]["records"],
        },
        "grade": {
            "celulas_com_oceano": int((celulas["fracao_oceano"] > 0.01).sum()),
            "area_oceano_milhoes_km2": float((celulas["area_0-200_km2"]).sum() / 1e6),
            "registros_nas_celulas": int(celulas["registros_total"].sum()),
            "registros_nas_unidades": total_unidades,
            "fracao_sem_profundidade_nas_celulas": 1 - total_unidades / int(celulas["registros_total"].sum()),
            "unidades_com_agua": int(len(com_agua)),
            "registros_em_unidades_sem_agua_no_relevo": int(unid.loc[~unid["tem_agua"], "registros"].sum()),
        },
    }

    por_faixa = {}
    for faixa in dados.ID_FAIXAS:
        u = com_agua[com_agua["faixa"] == faixa]
        area = float(u["area_faixa_km2"].sum())
        por_faixa[faixa] = {
            "rotulo": dados.ROTULO_FAIXA[faixa],
            "area_milhoes_km2": area / 1e6,
            "registros": int(u["registros"].sum()),
            "registros_por_mil_km2": float(u["registros"].sum() / area * 1000),
            "fracao_dos_registros": float(u["registros"].sum() / com_agua["registros"].sum()),
            "unidades": int(len(u)),
            "unidades_sem_registro": int((u["zona"] == ZONAS[0]).sum()),
            "unidades_insuficientes": int((u["zona"] == ZONAS[1]).sum()),
            "unidades_avaliaveis": int((u["zona"] == ZONAS[2]).sum()),
            "fracao_da_area_sem_registro": float(u.loc[u["zona"] == ZONAS[0], "area_faixa_km2"].sum() / area),
            "fracao_da_area_sem_inventario": float(u.loc[u["zona"] != ZONAS[2], "area_faixa_km2"].sum() / area),
            "gini": esforco.gini(u["registros"], u["area_faixa_km2"]),
            "densidade_mediana": float(u["densidade"].median()),
        }
    saida["por_faixa"] = por_faixa
    sem_inventario = sum(f["unidades_sem_registro"] + f["unidades_insuficientes"] for f in por_faixa.values())
    saida["sem_inventario"] = {
        "unidades": int(sem_inventario),
        "de": int(len(com_agua)),
        "fracao_das_unidades": sem_inventario / len(com_agua),
        "unidades_sem_registro": int(sum(f["unidades_sem_registro"] for f in por_faixa.values())),
        "fracao_da_area": float(com_agua.loc[com_agua["zona"] != ZONAS[2], "area_faixa_km2"].sum() / com_agua["area_faixa_km2"].sum()),
    }
    raso, fundo = por_faixa["0-200"]["registros_por_mil_km2"], por_faixa["4000+"]["registros_por_mil_km2"]
    saida["razao_superficie_fundo"] = raso / fundo if fundo > 0 else None

    por_hemisferio = {}
    for hemisferio in ("Norte", "Sul"):
        linha = {}
        for faixa in dados.ID_FAIXAS:
            u = com_agua[(com_agua["faixa"] == faixa) & (com_agua["hemisferio"] == hemisferio)]
            linha[faixa] = float(u["registros"].sum() / u["area_faixa_km2"].sum() * 1000)
        u = com_agua[com_agua["hemisferio"] == hemisferio]
        linha["registros"] = int(u["registros"].sum())
        linha["fracao_dos_registros"] = float(u["registros"].sum() / com_agua["registros"].sum())
        linha["fracao_da_area_superficial"] = float(
            u.loc[u["faixa"] == "0-200", "area_faixa_km2"].sum() / com_agua.loc[com_agua["faixa"] == "0-200", "area_faixa_km2"].sum()
        )
        por_hemisferio[hemisferio] = linha
    saida["por_hemisferio"] = por_hemisferio
    saida["razao_norte_sul_superficie"] = por_hemisferio["Norte"]["0-200"] / por_hemisferio["Sul"]["0-200"]

    # Desigualdade olhando a célula inteira (todos os registros, com e sem profundidade).
    cel = celulas[celulas["area_0-200_km2"] >= AREA_MINIMA_KM2]
    saida["desigualdade_celulas"] = {
        "celulas": int(len(cel)),
        "gini": esforco.gini(cel["registros_total"], cel["area_0-200_km2"]),
        "fracao_da_area_com_metade_dos_registros": esforco.fracao_da_area_com_metade(cel["registros_total"], cel["area_0-200_km2"]),
        "fracao_dos_registros_nos_10pct_da_area": esforco.fracao_dos_registros_no_topo(cel["registros_total"], cel["area_0-200_km2"], 0.1),
        "fracao_dos_registros_na_metade_menos_amostrada": 1
        - esforco.fracao_dos_registros_no_topo(cel["registros_total"], cel["area_0-200_km2"], 0.5),
        "celulas_sem_registro": int((cel["registros_total"] == 0).sum()),
    }
    saida["desigualdade_unidades"] = {
        "gini": esforco.gini(com_agua["registros"], com_agua["area_faixa_km2"]),
        "fracao_da_area_com_metade_dos_registros": esforco.fracao_da_area_com_metade(com_agua["registros"], com_agua["area_faixa_km2"]),
    }
    return saida


def curvas_de_lorenz(unid: pd.DataFrame, celulas: pd.DataFrame, pontos: int = 100) -> dict[str, list[list[float]]]:
    """Curva de Lorenz por faixa de profundidade e da célula inteira ("todas": todos os registros,
    com e sem profundidade), reduzida a `pontos` pontos para o gráfico."""
    grade = np.linspace(0, 1, pontos + 1)
    cel = celulas[celulas["area_0-200_km2"] >= AREA_MINIMA_KM2]
    x, y = esforco.curva_de_lorenz(cel["registros_total"], cel["area_0-200_km2"])
    saida = {"todas": [[float(a), float(b)] for a, b in zip(grade, np.interp(grade, x, y))]}
    for faixa in dados.ID_FAIXAS:
        u = unid[unid["tem_agua"] & (unid["faixa"] == faixa)]
        x, y = esforco.curva_de_lorenz(u["registros"], u["area_faixa_km2"])
        saida[faixa] = [[float(a), float(b)] for a, b in zip(grade, np.interp(grade, x, y))]
    return saida


# ----------------------------------------------------------------------------------------------
# 2 e 3. Completude e retorno esperado
# ----------------------------------------------------------------------------------------------


def estimar_unidade(x: np.ndarray, rng: np.random.Generator, repeticoes: int = REPETICOES) -> dict:
    """Todos os estimadores de uma unidade, com intervalo."""
    n, s, f1, f2 = riqueza.resumo(x)
    chao = riqueza.chao1(x)
    chao_inf, chao_sup = riqueza.intervalo_chao1(x)
    ace = riqueza.ace(x)
    novas = riqueza.novas_por_mil(x, extra=EXTRA)
    replicas = riqueza.bootstrap_resumos(x, repeticoes, rng)
    novas_rep = riqueza.novas_esperadas(replicas["n"], replicas["s"], replicas["f1"], replicas["f2"], EXTRA)
    novas_inf, novas_sup = riqueza.intervalo_bootstrap(novas, novas_rep)
    return {
        "singletons": f1,
        "doubletons": f2,
        "chao1": chao,
        "chao1_inf": chao_inf,
        "chao1_sup": chao_sup,
        "ace": ace,
        "jackknife1": riqueza.jackknife1(x),
        "cobertura": riqueza.cobertura(x),
        "completude": s / chao,
        "completude_inf": s / chao_sup,
        "completude_sup": s / chao_inf,
        "completude_ace": s / ace,
        "novas_por_mil": novas,
        "novas_por_mil_inf": novas_inf,
        "novas_por_mil_sup": novas_sup,
        "novas_por_mil_ace": riqueza.novas_por_mil(x, f0=ace - s, extra=EXTRA),
        "novas_por_mil_good_turing": EXTRA * f1 / n,
        "riqueza_cobertura_90": riqueza.riqueza_na_cobertura(x, 0.90),
        "registros_para_cobertura_95": riqueza.registros_para_cobertura(x, 0.95),
    }


def _posto(valores: pd.Series, maior_primeiro: bool = True) -> np.ndarray:
    return rankdata(-valores if maior_primeiro else valores, method="min").astype(int)


def estimar(unid: pd.DataFrame, contagens: dict, rng: np.random.Generator, repeticoes: int = REPETICOES) -> pd.DataFrame:
    """Tabela das unidades avaliáveis, com estimadores e os postos de cada regra de prioridade.

    - posto: pelo retorno esperado (espécies novas por mil registros, extrapolação com Chao1);
    - posto_ace e posto_good_turing: o mesmo com outro estimador;
    - posto_menos_registros e posto_mais_especies: as duas linhas de base ingênuas.
    """
    aval = unid[unid["zona"] == ZONAS[2]].copy()
    estimativas = [estimar_unidade(contagens[(c, f)], rng, repeticoes) for c, f in zip(aval["celula"], aval["faixa"])]
    aval = pd.concat([aval.reset_index(drop=True), pd.DataFrame(estimativas)], axis=1)
    aval["fracao_acima_de_especie"] = 1 - aval["registros_especie"] / aval["registros"]
    aval["fracao_so_genero"] = aval["registros_genero"] / aval["registros"]
    aval["posto"] = _posto(aval["novas_por_mil"])
    aval["posto_ace"] = _posto(aval["novas_por_mil_ace"])
    aval["posto_good_turing"] = _posto(aval["novas_por_mil_good_turing"])
    aval["posto_menos_registros"] = _posto(aval["registros_especie"], maior_primeiro=False)
    aval["posto_mais_especies"] = _posto(aval["especies"])
    # Alerta: um único conjunto de dados responde por metade ou mais dos registros da unidade. Uma
    # compilação de literatura, por exemplo, entra com um registro por espécie e enche a amostra de
    # singletons sem que isso diga algo sobre a comunidade.
    aval["alerta_conjunto_dominante"] = aval["fracao_maior_conjunto"] >= DOMINANCIA_ALTA
    aval["posto_sem_alerta"] = np.nan
    limpas = ~aval["alerta_conjunto_dominante"]
    aval.loc[limpas, "posto_sem_alerta"] = _posto(aval.loc[limpas, "novas_por_mil"])
    aval["posto_sem_alerta"] = aval["posto_sem_alerta"].astype("Int64")
    return aval.sort_values(["posto", "celula", "faixa"]).reset_index(drop=True)


def spearman(a, b) -> float:
    """Correlação de postos de Spearman (Pearson sobre os postos médios)."""
    ra, rb = rankdata(a), rankdata(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


REGRAS = {
    "retorno (Chao1)": ("novas_por_mil", True),
    "retorno (ACE)": ("novas_por_mil_ace", True),
    "retorno (Good-Turing)": ("novas_por_mil_good_turing", True),
    "menos registros": ("registros_especie", False),
    "mais espécies registradas": ("especies", True),
}


def comparar_rankings(aval: pd.DataFrame, topo: int = TOPO) -> dict:
    """Quanto os rankings concordam: Spearman entre as regras e sobreposição das listas curtas."""
    topos = {}
    for nome, (coluna, maior) in REGRAS.items():
        ordem = aval.sort_values(coluna, ascending=not maior, kind="stable")
        topos[nome] = set(zip(ordem["celula"].head(topo), ordem["faixa"].head(topo)))
    principal = "retorno (Chao1)"
    saida = {"unidades": int(len(aval)), "topo": topo, "contra_o_retorno_chao1": {}}
    for nome, (coluna, maior) in REGRAS.items():
        if nome == principal:
            continue
        sinal = 1 if maior else -1
        saida["contra_o_retorno_chao1"][nome] = {
            "spearman": spearman(aval["novas_por_mil"], sinal * aval[coluna]),
            "em_comum_no_topo": len(topos[principal] & topos[nome]),
        }
    saida["spearman_menos_registros_x_mais_especies"] = spearman(-aval["registros_especie"], aval["especies"])
    saida["em_comum_menos_registros_x_mais_especies"] = len(topos["menos registros"] & topos["mais espécies registradas"])
    saida["no_topo_das_tres"] = len(topos[principal] & topos["menos registros"] & topos["mais espécies registradas"])
    saida["maior_troca_de_posto_chao1_ace"] = int((aval["posto"] - aval["posto_ace"]).abs().max())
    saida["mediana_troca_de_posto_chao1_ace"] = float((aval["posto"] - aval["posto_ace"]).abs().median())
    saida["spearman_retorno_x_registros"] = spearman(aval["novas_por_mil"], aval["registros_especie"])
    saida["spearman_retorno_x_completude"] = spearman(aval["novas_por_mil"], aval["completude"])
    return saida


def resumo_da_completude(aval: pd.DataFrame) -> dict:
    return {
        "unidades": int(len(aval)),
        "completude_mediana": float(aval["completude"].median()),
        "completude_p10": float(aval["completude"].quantile(0.1)),
        "completude_p90": float(aval["completude"].quantile(0.9)),
        "unidades_acima_de_80pct": int((aval["completude"] >= 0.8).sum()),
        "unidades_abaixo_de_50pct": int((aval["completude"] < 0.5).sum()),
        "cobertura_mediana": float(aval["cobertura"].median()),
        "razao_mediana_ace_chao1": float((aval["ace"] / aval["chao1"]).median()),
        "razao_mediana_jackknife_chao1": float((aval["jackknife1"] / aval["chao1"]).median()),
        "novas_por_mil_mediana": float(aval["novas_por_mil"].median()),
        "novas_por_mil_p90": float(aval["novas_por_mil"].quantile(0.9)),
        "por_faixa": {
            faixa: {
                "unidades": int(len(g)),
                "completude_mediana": float(g["completude"].median()),
                "cobertura_mediana": float(g["cobertura"].median()),
                "novas_por_mil_mediana": float(g["novas_por_mil"].median()),
            }
            for faixa, g in aval.groupby("faixa")
        },
    }


# ----------------------------------------------------------------------------------------------
# 5. Validação no tempo
# ----------------------------------------------------------------------------------------------


def tabela_de_validacao(
    unid: pd.DataFrame, contagens_antes: dict, contagens_novas: dict, rng: np.random.Generator, repeticoes: int = REPETICOES
) -> pd.DataFrame:
    """Para cada unidade com dado suficiente antes e depois do corte: o previsto com o que se sabia
    até o corte e o realizado depois.

    Previsto: espécies novas nos próximos mil registros, só com os registros até o ano de corte.
    Realizado: das espécies que apareceram na unidade só depois do corte, quantas estariam em mil
    registros sorteados entre os posteriores (rarefação exata). Assim todas as unidades são
    comparadas no mesmo esforço, mil registros, qualquer que tenha sido o esforço real depois.
    """
    base = unid.dropna(subset=["registros_especie_depois_corte"]).copy()
    base = base[(base["registros_especie_ate_corte"] >= MIN_REGISTROS) & (base["registros_especie_depois_corte"] >= MIN_POSTERIORES)]
    linhas = []
    for u in base.itertuples():
        x = contagens_antes[(u.celula, u.faixa)]
        n, s, f1, f2 = riqueza.resumo(x)
        novas = contagens_novas.get((u.celula, u.faixa), np.array([], dtype=np.int64))
        posteriores = int(u.registros_especie_depois_corte)
        previsto = riqueza.novas_por_mil(x, extra=EXTRA)
        replicas = riqueza.bootstrap_resumos(x, repeticoes, rng)
        rep = riqueza.novas_esperadas(replicas["n"], replicas["s"], replicas["f1"], replicas["f2"], EXTRA)
        inf, sup = riqueza.intervalo_bootstrap(previsto, rep)
        ace = riqueza.ace(x)
        linhas.append(
            {
                "celula": u.celula,
                "faixa": u.faixa,
                "rotulo": u.rotulo,
                "registros_antes": n,
                "especies_antes": s,
                "registros_depois": posteriores,
                "previsto": previsto,
                "previsto_inf": inf,
                "previsto_sup": sup,
                "previsto_ace": riqueza.novas_por_mil(x, f0=ace - s, extra=EXTRA),
                "previsto_good_turing": EXTRA * f1 / n,
                "realizado": riqueza.rarefacao_parcial(novas, posteriores, EXTRA),
                "novas_no_total": int(len(novas)),
                "previsto_no_total": float(riqueza.novas_esperadas(n, s, f1, f2, posteriores)),
                "dentro_do_dobro": bool(posteriores <= 2 * n),
                "completude_antes": s / riqueza.chao1(x),
                "fracao_maior_conjunto": u.fracao_maior_conjunto,
            }
        )
    return pd.DataFrame(linhas)


REGRAS_VALIDACAO = {
    "retorno (Chao1)": ("previsto", 1),
    "retorno (ACE)": ("previsto_ace", 1),
    "retorno (Good-Turing)": ("previsto_good_turing", 1),
    "menos registros": ("registros_antes", -1),
    "mais espécies registradas": ("especies_antes", 1),
}


def avaliar_validacao(val: pd.DataFrame, rng: np.random.Generator, reamostras: int = 2000, topo: int = TOPO) -> dict:
    """O ranking presta? Spearman de cada regra com o realizado, com intervalo por bootstrap das
    unidades, a diferença para cada linha de base, o rendimento da lista curta e a calibração."""
    n = len(val)
    realizado = val["realizado"].to_numpy()
    pontuacao = {nome: sinal * val[coluna].to_numpy() for nome, (coluna, sinal) in REGRAS_VALIDACAO.items()}
    indices = rng.integers(0, n, size=(reamostras, n))
    reps = {nome: np.array([spearman(p[i], realizado[i]) for i in indices]) for nome, p in pontuacao.items()}
    principal = "retorno (Chao1)"
    regras = {}
    for nome, p in pontuacao.items():
        ordem = np.argsort(-p, kind="stable")[:topo]
        linha = {
            "spearman": spearman(p, realizado),
            "spearman_inf": float(np.nanpercentile(reps[nome], 2.5)),
            "spearman_sup": float(np.nanpercentile(reps[nome], 97.5)),
            "realizado_medio_no_topo": float(realizado[ordem].mean()),
            "acertos_no_topo": int(len(set(ordem) & set(np.argsort(-realizado, kind="stable")[:topo]))),
        }
        if nome != principal:
            dif = reps[principal] - reps[nome]
            linha["vantagem_do_retorno_chao1"] = float(spearman(pontuacao[principal], realizado) - linha["spearman"])
            linha["vantagem_inf"] = float(np.nanpercentile(dif, 2.5))
            linha["vantagem_sup"] = float(np.nanpercentile(dif, 97.5))
        regras[nome] = linha
    por_faixa = {}
    if "faixa" in val:
        for faixa, g in val.groupby("faixa"):
            if len(g) >= 20:
                por_faixa[faixa] = {
                    "unidades": int(len(g)),
                    "spearman_retorno_chao1": spearman(g["previsto"], g["realizado"]),
                    "spearman_menos_registros": spearman(-g["registros_antes"], g["realizado"]),
                }
    razao = (val["realizado"] + 0.5) / (val["previsto"] + 0.5)
    dentro = val[val["dentro_do_dobro"]]
    razao_total = (val["novas_no_total"] + 0.5) / (val["previsto_no_total"] + 0.5)
    return {
        "unidades": int(n),
        "ano_de_corte": dados.ANO_DE_CORTE,
        "topo": topo,
        "regras": regras,
        "por_faixa": por_faixa,
        "realizado_medio_geral": float(realizado.mean()),
        "realizado_medio_do_melhor_topo_possivel": float(np.sort(realizado)[::-1][:topo].mean()),
        "calibracao_por_mil": {
            "previsto_mediano": float(val["previsto"].median()),
            "realizado_mediano": float(val["realizado"].median()),
            "razao_mediana_realizado_previsto": float(razao.median()),
            "razao_p25": float(razao.quantile(0.25)),
            "razao_p75": float(razao.quantile(0.75)),
            "fracao_dentro_do_intervalo": float(((val["realizado"] >= val["previsto_inf"]) & (val["realizado"] <= val["previsto_sup"])).mean()),
            "fracao_realizado_acima_do_intervalo": float((val["realizado"] > val["previsto_sup"]).mean()),
            "fracao_realizado_abaixo_do_intervalo": float((val["realizado"] < val["previsto_inf"]).mean()),
            "fracao_dentro_de_um_fator_2": float(((razao >= 0.5) & (razao <= 2)).mean()),
        },
        "calibracao_no_total": {
            "unidades_dentro_do_dobro": int(len(dentro)),
            "razao_mediana_todas": float(razao_total.median()),
            "razao_mediana_dentro_do_dobro": float(razao_total[val["dentro_do_dobro"]].median()) if len(dentro) else None,
            "razao_mediana_alem_do_dobro": float(razao_total[~val["dentro_do_dobro"]].median()) if len(dentro) < n else None,
            "novas_realizadas_total": int(val["novas_no_total"].sum()),
            "novas_previstas_total": float(val["previsto_no_total"].sum()),
        },
        "spearman_erro_x_dominancia": spearman(np.log(razao), val["fracao_maior_conjunto"]),
    }


# ----------------------------------------------------------------------------------------------
# 6. Vieses
# ----------------------------------------------------------------------------------------------


def vieses(unid: pd.DataFrame, aval: pd.DataFrame, topo: int = TOPO) -> dict:
    """Mede os vieses que o estudo declara: conjunto dominante e identificação acima de espécie."""
    com_registro = unid[unid["registros"] > 0]
    lista = aval.head(topo)
    dominadas = aval[aval["fracao_maior_conjunto"] >= DOMINANCIA_ALTA]
    return {
        "conjunto_dominante": {
            "limiar": DOMINANCIA_ALTA,
            "fracao_mediana_do_maior_conjunto": float(aval["fracao_maior_conjunto"].median()),
            "unidades_avaliaveis_dominadas": int(len(dominadas)),
            "fracao_das_avaliaveis_dominadas": float(len(dominadas) / len(aval)),
            "dominadas_no_topo": int((lista["fracao_maior_conjunto"] >= DOMINANCIA_ALTA).sum()),
            "spearman_completude_x_dominancia": spearman(aval["completude"], aval["fracao_maior_conjunto"]),
            "spearman_retorno_x_dominancia": spearman(aval["novas_por_mil"], aval["fracao_maior_conjunto"]),
            "completude_mediana_dominadas": float(dominadas["completude"].median()) if len(dominadas) else None,
            "completude_mediana_demais": float(aval.loc[aval["fracao_maior_conjunto"] < DOMINANCIA_ALTA, "completude"].median()),
        },
        "identificacao": {
            "fracao_acima_de_especie": float(1 - com_registro["registros_especie"].sum() / com_registro["registros"].sum()),
            "fracao_so_genero": float(com_registro["registros_genero"].sum() / com_registro["registros"].sum()),
            "fracao_acima_de_especie_por_faixa": {
                faixa: float(1 - g["registros_especie"].sum() / g["registros"].sum()) for faixa, g in com_registro.groupby("faixa")
            },
            "unidades_que_seriam_avaliaveis_com_os_registros_de_genero": int(
                ((com_registro["registros_especie"] < MIN_REGISTROS) & (com_registro["registros_especie"] + com_registro["registros_genero"] >= MIN_REGISTROS)).sum()
            ),
            "spearman_retorno_x_fracao_acima_de_especie": spearman(aval["novas_por_mil"], aval["fracao_acima_de_especie"]),
        },
    }


# ----------------------------------------------------------------------------------------------
# Simulação: comunidades de riqueza conhecida
# ----------------------------------------------------------------------------------------------

RIQUEZA_SIMULADA = 2000
TAMANHOS_SIMULADOS = [100, 300, 1000, 3000, 10_000, 30_000, 100_000]
COMUNIDADES = {"equilibrada": 1.0, "muitas raras": 2.5}  # desvio-padrão do log da abundância


def comunidade_simulada(desvio: float, especies: int = RIQUEZA_SIMULADA, semente: int = SEMENTE) -> np.ndarray:
    """Abundâncias relativas log-normais de uma comunidade com número de espécies conhecido."""
    p = np.random.default_rng(semente).lognormal(0.0, desvio, especies)
    return p / p.sum()


def simular(rng: np.random.Generator, repeticoes: int = 60) -> pd.DataFrame:
    """Os estimadores em comunidades de riqueza conhecida, do caso fácil ao caso em que falham.

    Para cada comunidade e tamanho de amostra: a razão média entre cada estimador e a riqueza
    verdadeira, com que frequência o intervalo do Chao1 contém a verdade, e a razão entre as
    espécies novas previstas para os próximos mil registros e as que de fato viriam (valor esperado
    exato, porque na simulação as abundâncias são conhecidas).
    """
    linhas = []
    for nome, desvio in COMUNIDADES.items():
        p = comunidade_simulada(desvio)
        for n in TAMANHOS_SIMULADOS:
            acumulado = {k: [] for k in ("observada", "chao1", "ace", "jackknife1", "cobre", "previstas", "verdadeiras", "cobertura_estimada", "cobertura_real")}
            for _ in range(repeticoes):
                amostra = rng.multinomial(n, p)
                x = amostra[amostra > 0]
                inf, sup = riqueza.intervalo_chao1(x)
                acumulado["observada"].append(x.size)
                acumulado["chao1"].append(riqueza.chao1(x))
                acumulado["ace"].append(riqueza.ace(x))
                acumulado["jackknife1"].append(riqueza.jackknife1(x))
                acumulado["cobre"].append(inf <= RIQUEZA_SIMULADA <= sup)
                acumulado["previstas"].append(riqueza.novas_por_mil(x, extra=EXTRA))
                acumulado["verdadeiras"].append(float((1 - (1 - p[amostra == 0]) ** EXTRA).sum()))
                acumulado["cobertura_estimada"].append(riqueza.cobertura(x))
                acumulado["cobertura_real"].append(float(p[amostra > 0].sum()))
            m = {k: float(np.mean(v)) for k, v in acumulado.items()}
            linhas.append(
                {
                    "comunidade": nome,
                    "registros": n,
                    "observada_sobre_real": m["observada"] / RIQUEZA_SIMULADA,
                    "chao1_sobre_real": m["chao1"] / RIQUEZA_SIMULADA,
                    "ace_sobre_real": m["ace"] / RIQUEZA_SIMULADA,
                    "jackknife1_sobre_real": m["jackknife1"] / RIQUEZA_SIMULADA,
                    "intervalo_chao1_contem_a_verdade": m["cobre"],
                    "cobertura_real": m["cobertura_real"],
                    "cobertura_estimada": m["cobertura_estimada"],
                    "novas_previstas_por_mil": m["previstas"],
                    "novas_verdadeiras_por_mil": m["verdadeiras"],
                    "previstas_sobre_verdadeiras": m["previstas"] / m["verdadeiras"] if m["verdadeiras"] > 0 else float("nan"),
                }
            )
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------------------------
# Arquivos reutilizáveis
# ----------------------------------------------------------------------------------------------

COLUNAS_PRIORITARIAS = [
    "posto", "celula", "rotulo", "lat_sul", "lon_oeste", "faixa", "registros", "registros_especie", "especies",
    "chao1", "chao1_inf", "chao1_sup", "ace", "completude", "completude_inf", "completude_sup", "cobertura",
    "novas_por_mil", "novas_por_mil_inf", "novas_por_mil_sup", "novas_por_mil_ace", "posto_ace",
    "posto_menos_registros", "posto_mais_especies", "registros_para_cobertura_95", "fracao_acima_de_especie",
    "fracao_oceano", "fracao_maior_conjunto", "maior_conjunto_titulo", "alerta_conjunto_dominante", "posto_sem_alerta",
]  # fmt: skip


def celulas_prioritarias(aval: pd.DataFrame) -> pd.DataFrame:
    """A tabela principal, pronta para reuso: uma linha por unidade avaliável, na ordem do retorno."""
    t = aval.copy()
    t["registros_para_cobertura_95"] = t["registros_para_cobertura_95"].replace(np.inf, np.nan).round(0)
    t = t[COLUNAS_PRIORITARIAS]
    arredondar = {c: 1 for c in ("chao1", "chao1_inf", "chao1_sup", "ace", "novas_por_mil", "novas_por_mil_inf", "novas_por_mil_sup", "novas_por_mil_ace")}
    arredondar |= {c: 3 for c in ("completude", "completude_inf", "completude_sup", "cobertura", "fracao_acima_de_especie", "fracao_maior_conjunto", "fracao_oceano")}
    return t.round(arredondar)


def lacunas(unid: pd.DataFrame) -> pd.DataFrame:
    """As unidades em que nenhum estimador tem o que dizer: sem registro ou com amostra insuficiente."""
    t = unid[unid["tem_agua"] & (unid["zona"] != ZONAS[2])].copy()
    t["area_faixa_km2"] = t["area_faixa_km2"].round(0)
    colunas = ["celula", "rotulo", "lat_sul", "lon_oeste", "faixa", "zona", "area_faixa_km2", "registros", "registros_especie", "especies"]
    return t[colunas].sort_values(["registros", "area_faixa_km2"], ascending=[True, False]).reset_index(drop=True)
