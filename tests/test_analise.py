"""A orquestração conferida com dados sintéticos em memória."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from oceano_lacunas import analise, dados


def _celulas() -> pd.DataFrame:
    linhas = []
    for lat, lon in [(0, 0), (-10, 0), (40, 0)]:
        area = dados.area_da_celula_km2(lat)
        linha = {"celula": dados.id_celula(lat, lon), "lat_sul": lat, "lon_oeste": lon, "area_km2": area, "fracao_oceano": 1.0}
        for faixa, fracao in zip(dados.ID_FAIXAS, (1.0, 1.0, 0.5, 0.0)):
            linha[f"area_{faixa}_km2"] = area * fracao
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _unidades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "celula": ["N00E000", "N00E000", "N40E000", "S10E000"],
            "faixa": ["0-200", "200-1000", "0-200", "4000+"],
            "registros": [5000, 100, 900, 7],
            "registros_especie": [4000, 60, 700, 5],
            "registros_genero": [600, 30, 100, 2],
            "especies": [300, 40, 150, 4],
            "fracao_maior_conjunto": [0.7, np.nan, 0.2, np.nan],
        }
    )


def test_montar_unidades_classifica_as_tres_zonas_e_guarda_registro_onde_o_relevo_nao_ve_agua():
    t = analise.montar_unidades(_celulas(), _unidades()).set_index(["celula", "faixa"])
    assert t.loc[("N00E000", "0-200"), "zona"] == "avaliável"
    assert t.loc[("N00E000", "200-1000"), "zona"] == "amostra insuficiente"
    assert t.loc[("S10E000", "0-200"), "zona"] == "sem registro"
    # 3 células x 3 faixas com água, mais a unidade com registro numa faixa sem água no relevo.
    assert len(t) == 10
    assert not t.loc[("S10E000", "4000+"), "tem_agua"]
    assert np.isnan(t.loc[("S10E000", "4000+"), "densidade"])
    assert t.loc[("N40E000", "0-200"), "hemisferio"] == "Norte" and t.loc[("S10E000", "0-200"), "hemisferio"] == "Sul"
    esperado = 5000 / dados.area_da_celula_km2(0) * 1000
    assert t.loc[("N00E000", "0-200"), "densidade"] == pytest.approx(esperado)


def test_spearman_em_casos_conhecidos():
    assert analise.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1)
    assert analise.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1)
    assert analise.spearman([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) == pytest.approx(0.8)
    assert np.isnan(analise.spearman([1, 1, 1], [1, 2, 3]))


def test_estimar_unidade_tem_intervalos_coerentes():
    rng = np.random.default_rng(0)
    x = np.repeat([1, 2, 5, 40], [300, 120, 80, 50])
    e = analise.estimar_unidade(x, rng, repeticoes=100)
    assert e["chao1_inf"] <= e["chao1"] <= e["chao1_sup"]
    assert e["completude_inf"] <= e["completude"] <= e["completude_sup"] <= 1
    assert 0 <= e["novas_por_mil_inf"] <= e["novas_por_mil"] <= e["novas_por_mil_sup"]
    assert e["novas_por_mil"] <= e["chao1"] - x.size  # não se espera mais espécie nova do que as não vistas
    assert e["novas_por_mil_good_turing"] == pytest.approx(1000 * 300 / x.sum())


def _avaliaveis(n: int = 30) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(1)
    celulas = pd.DataFrame(
        [{"celula": f"C{i:02d}", "lat_sul": 0, "lon_oeste": 0, "area_km2": 1e6, "fracao_oceano": 1.0}
         | {f"area_{f}_km2": 1e6 for f in dados.ID_FAIXAS} for i in range(n)]
    )  # fmt: skip
    contagens, linhas = {}, []
    for i in range(n):
        p = rng.lognormal(0, 1.5, 400)
        sorteio = rng.multinomial(int(rng.integers(600, 6000)), p / p.sum())
        x = sorteio[sorteio > 0]
        contagens[(f"C{i:02d}", "0-200")] = x
        linhas.append(
            {"celula": f"C{i:02d}", "faixa": "0-200", "registros": int(x.sum() * 1.2), "registros_especie": int(x.sum()),
             "registros_genero": int(x.sum() * 0.1), "especies": int(x.size), "fracao_maior_conjunto": 0.3,
             "maior_conjunto_titulo": "x"}
        )  # fmt: skip
    return analise.montar_unidades(celulas, pd.DataFrame(linhas)), contagens


def test_estimar_ordena_pelo_retorno_e_calcula_os_postos_das_linhas_de_base():
    unid, contagens = _avaliaveis()
    aval = analise.estimar(unid, contagens, np.random.default_rng(2), repeticoes=30)
    assert len(aval) == 30
    assert aval["posto"].tolist() == sorted(aval["posto"].tolist())
    assert aval.iloc[0]["novas_por_mil"] == aval["novas_por_mil"].max()
    assert aval.loc[aval["posto_menos_registros"] == 1, "registros_especie"].iloc[0] == aval["registros_especie"].min()
    assert aval.loc[aval["posto_mais_especies"] == 1, "especies"].iloc[0] == aval["especies"].max()
    comparacao = analise.comparar_rankings(aval, topo=5)
    assert -1 <= comparacao["contra_o_retorno_chao1"]["menos registros"]["spearman"] <= 1
    assert 0 <= comparacao["no_topo_das_tres"] <= 5
    tabela = analise.celulas_prioritarias(aval)
    assert list(tabela.columns) == analise.COLUNAS_PRIORITARIAS
    assert tabela["posto"].iloc[0] == 1


def test_avaliar_validacao_reconhece_previsao_perfeita_e_previsao_invertida():
    rng = np.random.default_rng(3)
    n = 40
    realizado = rng.gamma(2.0, 20.0, n)
    val = pd.DataFrame(
        {
            "previsto": realizado,
            "previsto_inf": realizado * 0.8,
            "previsto_sup": realizado * 1.2,
            "previsto_ace": realizado * 1.1,
            "previsto_good_turing": realizado * 1.5,
            "registros_antes": realizado,  # "menos registros" fica exatamente invertida
            "especies_antes": rng.normal(size=n),
            "realizado": realizado,
            "novas_no_total": (realizado * 3).round(),
            "previsto_no_total": realizado * 3,
            "dentro_do_dobro": np.arange(n) % 2 == 0,
            "fracao_maior_conjunto": rng.uniform(size=n),
        }
    )
    r = analise.avaliar_validacao(val, rng, reamostras=200, topo=5)
    assert r["regras"]["retorno (Chao1)"]["spearman"] == pytest.approx(1)
    assert r["regras"]["retorno (Chao1)"]["acertos_no_topo"] == 5
    assert r["regras"]["menos registros"]["spearman"] == pytest.approx(-1)
    assert r["regras"]["menos registros"]["vantagem_do_retorno_chao1"] == pytest.approx(2)
    assert r["regras"]["menos registros"]["vantagem_inf"] > 0
    assert r["calibracao_por_mil"]["razao_mediana_realizado_previsto"] == pytest.approx(1)
    assert r["calibracao_por_mil"]["fracao_dentro_do_intervalo"] == 1
    assert r["realizado_medio_do_melhor_topo_possivel"] == pytest.approx(r["regras"]["retorno (Chao1)"]["realizado_medio_no_topo"])


def test_tabela_de_validacao_preve_com_o_passado_e_mede_o_realizado_no_mesmo_esforco():
    rng = np.random.default_rng(4)
    unid = pd.DataFrame(
        {
            "celula": ["A", "B"], "faixa": ["0-200", "0-200"], "rotulo": ["a", "b"],
            "registros_especie_ate_corte": [1000, 100], "registros_especie_depois_corte": [2000, 5000],
            "fracao_maior_conjunto": [0.4, 0.4],
        }
    )  # fmt: skip
    antes = {("A", "0-200"): np.repeat([1, 2, 16], [200, 100, 37]), ("B", "0-200"): np.repeat([1], [100])}
    novas = {("A", "0-200"): np.repeat([1, 10], [50, 5])}
    val = analise.tabela_de_validacao(unid, antes, novas, rng, repeticoes=30)
    assert val["celula"].tolist() == ["A"]  # B tem menos de 500 registros antes do corte
    linha = val.iloc[0]
    assert linha["registros_antes"] == 992 and linha["novas_no_total"] == 55
    # Em mil dos 2.000 registros posteriores: cada espécie de 1 registro aparece com chance 1/2.
    assert 25 < linha["realizado"] < 55
    assert bool(linha["dentro_do_dobro"]) is False
    assert linha["previsto_inf"] <= linha["previsto"] <= linha["previsto_sup"]


def test_simulacao_mostra_a_falha_em_amostra_pequena_e_o_acerto_em_amostra_grande():
    sim = analise.simular(np.random.default_rng(5), repeticoes=5).set_index(["comunidade", "registros"])
    assert sim.loc[("muitas raras", 300), "chao1_sobre_real"] < 0.5
    assert sim.loc[("equilibrada", 100_000), "chao1_sobre_real"] == pytest.approx(1, abs=0.1)
    assert sim.loc[("equilibrada", 100), "observada_sobre_real"] < sim.loc[("equilibrada", 100), "chao1_sobre_real"]


def test_lacunas_lista_so_o_que_tem_agua_e_nao_e_avaliavel():
    t = analise.lacunas(analise.montar_unidades(_celulas(), _unidades()))
    assert set(t["zona"]) == {"sem registro", "amostra insuficiente"}
    assert ("S10E000", "4000+") not in set(zip(t["celula"], t["faixa"]))
    assert t["registros"].is_monotonic_increasing
