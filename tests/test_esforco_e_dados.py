"""Desigualdade do esforço e funções de grade e agregação, sem rede e sem arquivo."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from oceano_lacunas import dados, esforco


def test_gini_zero_com_esforco_uniforme():
    assert esforco.gini([10, 20, 30], [1, 2, 3]) == pytest.approx(0)


def test_gini_com_tudo_numa_unidade_de_n_iguais():
    # Tudo em 1 de 5 unidades de mesma área: Gini = 1 − 1/5.
    assert esforco.gini([0, 0, 0, 0, 100], [1, 1, 1, 1, 1]) == pytest.approx(0.8)


def test_gini_nao_muda_com_a_escala_nem_com_a_ordem():
    r, a = np.array([5, 1, 30, 0, 12]), np.array([2.0, 1.0, 1.5, 4.0, 1.0])
    ordem = np.array([3, 0, 4, 1, 2])
    assert esforco.gini(r, a) == pytest.approx(esforco.gini(1000 * r[ordem], 7 * a[ordem]))


def test_curva_de_lorenz_vai_de_zero_a_um_e_fica_abaixo_da_diagonal():
    x, y = esforco.curva_de_lorenz([1, 5, 50, 0], [1, 1, 1, 1])
    assert (x[0], y[0], x[-1], y[-1]) == (0, 0, 1, 1)
    assert np.all(y <= x + 1e-12)


def test_fracoes_de_concentracao():
    registros, area = [0, 0, 10, 90], [1, 1, 1, 1]
    # A unidade mais densa (25% da área) tem 90%; metade dos registros cabe em 50/90 dela.
    assert esforco.fracao_dos_registros_no_topo(registros, area, 0.25) == pytest.approx(0.9)
    assert esforco.fracao_da_area_com_metade(registros, area) == pytest.approx(0.25 * 50 / 90)


def test_lorenz_recusa_area_nula():
    with pytest.raises(ValueError):
        esforco.curva_de_lorenz([1, 2], [0, 1])


def test_area_das_celulas_soma_a_esfera_e_encolhe_com_a_latitude():
    total = sum(dados.area_da_celula_km2(lat) * 36 for lat in range(-90, 90, 10))
    assert total == pytest.approx(4 * np.pi * dados.RAIO_TERRA_KM**2)
    assert dados.area_da_celula_km2(0) == pytest.approx(dados.area_da_celula_km2(-10))
    assert dados.area_da_celula_km2(80) / dados.area_da_celula_km2(0) == pytest.approx(0.0875, abs=0.001)


def test_identificador_rotulo_e_poligono_da_celula():
    assert dados.id_celula(40, -30) == "N40W030"
    assert dados.id_celula(-10, 120) == "S10E120"
    assert dados.rotulo_celula(-10, -10) == "10°S a 0°, 10°W a 0°"
    assert dados.rotulo_celula(80, 170) == "80°N a 90°N, 170°E a 180°"
    assert dados.poligono(0, 10) == "POLYGON((10 0, 20 0, 20 10, 10 10, 10 0))"


def test_faixas_de_profundidade_nao_se_sobrepoem():
    limites = [(a, b) for _, _, a, b in dados.FAIXAS]
    assert all(fim + 1 == limites[i + 1][0] for i, (_, fim) in enumerate(limites[:-1]))


def test_grade_mede_a_fracao_de_oceano_e_de_cada_faixa():
    # Uma célula (0° a 10°N, 0° a 10°E): metade oeste em terra, metade leste com fundo a 3.000 m.
    lat, lon = np.meshgrid(np.arange(0.25, 10, 0.5), np.arange(0.25, 10, 0.5), indexing="ij")
    relevo = pd.DataFrame({"latitude": lat.ravel(), "longitude": lon.ravel()})
    relevo["altitude"] = np.where(relevo["longitude"] < 5, 150.0, -3000.0)
    grade = dados.grade_de_celulas(relevo)
    assert len(grade) == 1
    c = grade.iloc[0]
    assert c["celula"] == "N00E000"
    assert c["fracao_oceano"] == pytest.approx(0.5)
    assert c["fracao_1000-4000"] == pytest.approx(0.5)
    assert c["fracao_4000+"] == 0
    assert c["area_200-1000_km2"] == pytest.approx(0.5 * dados.area_da_celula_km2(0))


def test_resumo_do_checklist_soma_subespecie_na_especie_e_separa_o_que_nao_chega_a_especie():
    linhas = [
        {"taxonRank": "Species", "speciesid": 10, "records": 5},
        {"taxonRank": "Subspecies", "speciesid": 10, "records": 2},
        {"taxonRank": "Species", "speciesid": 11, "records": 1},
        {"taxonRank": "Genus", "records": 7},
        {"taxonRank": "Family", "records": 3},
    ]
    r = dados.resumir_checklist(linhas)
    assert r["registros"] == 18
    assert r["registros_especie"] == 8
    assert r["registros_genero"] == 7
    assert r["contagens"] == [(10, 7), (11, 1)]


def test_histograma_e_reconstrucao_das_contagens():
    assert dados.histograma([1, 1, 2, 5, 5, 5]) == {1: 2, 2: 1, 5: 3}
    freq = pd.DataFrame(
        {"celula": ["A"] * 3, "faixa": ["0-200"] * 3, "periodo": ["todos"] * 3, "k": [1, 2, 5], "f": [2, 1, 3]}
    )
    x = dados.frequencias_da_unidade(freq)[("A", "0-200")]
    assert sorted(x.tolist()) == [1, 1, 2, 5, 5, 5]
