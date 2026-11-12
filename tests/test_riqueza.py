"""Estimadores conferidos contra contas feitas à mão e contra comunidades de riqueza conhecida."""

from __future__ import annotations

import numpy as np
import pytest

from oceano_lacunas import riqueza

# n = 23, S = 8, f1 = 4, f2 = 2
AMOSTRA = [1, 1, 1, 1, 2, 2, 5, 10]


def test_resumo_conta_registros_especies_singletons_e_doubletons():
    assert riqueza.resumo(AMOSTRA) == (23, 8, 4, 2)
    assert riqueza.resumo([0, 3, 0]) == (3, 1, 0, 0)


def test_chao1_com_doubletons_confere_com_a_conta_a_mao():
    # S + (n−1)/n · f1²/(2·f2) = 8 + (22/23) · 16/4
    assert riqueza.chao1(AMOSTRA) == pytest.approx(8 + 22 / 23 * 4)


def test_chao1_sem_doubletons_usa_a_forma_corrigida():
    # n = 8, f1 = 3, f2 = 0: 4 + (7/8) · 3·2/2
    assert riqueza.chao1([1, 1, 1, 5]) == pytest.approx(4 + 7 / 8 * 3)


def test_chao1_sem_singletons_devolve_a_riqueza_observada():
    x = [2, 3, 4, 10]
    assert riqueza.chao1(x) == 4
    assert riqueza.intervalo_chao1(x) == (4.0, 4.0)


def test_intervalo_do_chao1_e_log_normal_e_nunca_fica_abaixo_do_observado():
    n, s, f1, f2 = riqueza.resumo(AMOSTRA)
    k, r = (n - 1) / n, f1 / f2
    var = f2 * (k * r**2 / 2 + k**2 * r**3 + k**2 * r**4 / 4)
    t = riqueza.chao1(AMOSTRA) - s
    fator = np.exp(1.959963984540054 * np.sqrt(np.log(1 + var / t**2)))
    inf, sup = riqueza.intervalo_chao1(AMOSTRA)
    assert inf == pytest.approx(s + t / fator)
    assert sup == pytest.approx(s + t * fator)
    assert s < inf < riqueza.chao1(AMOSTRA) < sup


def test_ace_confere_com_a_conta_a_mao():
    # Raras: [1, 1, 1, 1, 8, 9] (n_raras = 21, f1 = 4); abundantes: uma espécie com 30 registros.
    x = [1, 1, 1, 1, 8, 9, 30]
    c = 1 - 4 / 21
    gama2 = 6 / c * (8 * 7 + 9 * 8) / (21 * 20) - 1
    assert gama2 > 0
    assert riqueza.ace(x) == pytest.approx(1 + 6 / c + 4 / c * gama2)


def test_ace_com_heterogeneidade_negativa_zera_a_correcao():
    x = [1, 1, 1, 2, 2, 3, 20]  # γ² sairia negativo
    assert riqueza.ace(x) == pytest.approx(1 + 6 / 0.7)


def test_ace_cai_no_chao1_quando_todas_as_raras_sao_singletons():
    x = [1, 1, 1, 50]
    assert riqueza.ace(x) == pytest.approx(riqueza.chao1(x))


def test_jackknife_de_primeira_ordem():
    assert riqueza.jackknife1(AMOSTRA) == pytest.approx(8 + 4 * 22 / 23)


def test_cobertura_de_good_turing_e_a_correcao_de_chao_e_jost():
    assert riqueza.cobertura_good_turing(AMOSTRA) == pytest.approx(1 - 4 / 23)
    assert riqueza.cobertura(AMOSTRA) == pytest.approx(1 - 4 / 23 * (22 * 4) / (22 * 4 + 2 * 2))
    assert riqueza.cobertura([5, 7, 9]) == 1.0
    # Só singletons (f2 = 0): forma corrigida, 1 − (3/3) · (2·2)/(2·2 + 2). O Good-Turing puro daria 0.
    assert riqueza.cobertura([1, 1, 1]) == pytest.approx(1 / 3)
    assert riqueza.cobertura_good_turing([1, 1, 1]) == 0


def test_rarefacao_nos_extremos_e_num_caso_enumeravel():
    assert riqueza.rarefacao(AMOSTRA, 23) == pytest.approx(8)
    assert riqueza.rarefacao(AMOSTRA, 1) == pytest.approx(1)
    assert riqueza.rarefacao(AMOSTRA, 0) == pytest.approx(0)
    # x = [2, 1, 1], m = 2: (1 − 1/6) + 2·(1 − 3/6) = 11/6
    assert riqueza.rarefacao([2, 1, 1], 2) == pytest.approx(11 / 6)


def test_rarefacao_confere_com_o_sorteio():
    rng = np.random.default_rng(1)
    x = np.array([40, 25, 10, 6, 3, 2, 2, 1, 1, 1])
    individuos = np.repeat(np.arange(x.size), x)
    sorteios = [np.unique(rng.choice(individuos, 20, replace=False)).size for _ in range(4000)]
    assert riqueza.rarefacao(x, 20) == pytest.approx(np.mean(sorteios), abs=0.08)


def test_rarefacao_recusa_tamanho_maior_que_a_amostra():
    with pytest.raises(ValueError):
        riqueza.rarefacao(AMOSTRA, 24)


def test_rarefacao_parcial_do_conjunto_inteiro_e_a_rarefacao():
    assert riqueza.rarefacao_parcial(AMOSTRA, 23, 10) == pytest.approx(riqueza.rarefacao(AMOSTRA, 10))
    # Subconjunto: uma espécie com 2 registros entre 4; em 2 sorteados aparece com chance 5/6.
    assert riqueza.rarefacao_parcial([2], 4, 2) == pytest.approx(5 / 6)
    assert riqueza.rarefacao_parcial([], 100, 10) == 0


def test_extrapolacao_parte_do_observado_cresce_e_satura_no_chao1():
    assert riqueza.extrapolacao(AMOSTRA, 0) == pytest.approx(8)
    curva = riqueza.extrapolacao(AMOSTRA, np.array([1, 5, 10, 50, 1e7]))
    assert np.all(np.diff(curva) > 0)
    assert curva[-1] == pytest.approx(riqueza.chao1(AMOSTRA), rel=1e-6)


def test_o_primeiro_registro_adicional_rende_cerca_de_f1_sobre_n():
    x = np.repeat([1, 2, 5, 40], [300, 120, 80, 50])
    n, _, f1, _ = riqueza.resumo(x)
    assert riqueza.novas_por_mil(x, extra=1) == pytest.approx(f1 / n, rel=0.01)


def test_novas_por_mil_com_outro_estimador_de_nao_vistas():
    # Com f0 informado a curva satura nele.
    assert riqueza.novas_por_mil(AMOSTRA, f0=2.0, extra=10**7) == pytest.approx(2.0)
    assert riqueza.novas_por_mil([3, 4, 5]) == 0  # sem singletons não se espera espécie nova


def test_cobertura_extrapolada_e_registros_para_cobertura_sao_inversas():
    assert riqueza.cobertura_extrapolada(AMOSTRA, 0) == pytest.approx(riqueza.cobertura(AMOSTRA))
    extra = riqueza.registros_para_cobertura(AMOSTRA, 0.95)
    assert extra > 0
    assert riqueza.cobertura_extrapolada(AMOSTRA, extra) == pytest.approx(0.95)
    assert riqueza.registros_para_cobertura(AMOSTRA, 0.5) == 0


def test_cobertura_rarefeita_cresce_com_o_tamanho_e_chega_perto_da_observada():
    valores = [riqueza.cobertura_rarefeita(AMOSTRA, m) for m in (2, 5, 10, 20, 22)]
    assert np.all(np.diff(valores) > 0)
    assert valores[-1] == pytest.approx(riqueza.cobertura(AMOSTRA), abs=0.03)


def test_riqueza_na_cobertura_rarefaz_extrapola_e_recusa_o_que_esta_longe():
    x = np.repeat([1, 2, 5, 40], [300, 120, 80, 50])
    c = riqueza.cobertura(x)
    assert riqueza.riqueza_na_cobertura(x, c) == pytest.approx(x.size, rel=0.01)
    assert riqueza.riqueza_na_cobertura(x, c - 0.1) < x.size  # rarefação
    assert riqueza.riqueza_na_cobertura(x, c + 0.02) > x.size  # extrapolação curta
    assert np.isnan(riqueza.riqueza_na_cobertura(x, 0.9999))  # pediria muito mais que o dobro


def test_comunidade_bootstrap_inclui_as_nao_vistas_e_soma_um():
    p = riqueza.comunidade_bootstrap(AMOSTRA)
    f0 = int(np.ceil(riqueza.chao1(AMOSTRA) - 8))
    assert p.size == 8 + f0
    assert p.sum() == pytest.approx(1)
    assert p[:8].sum() == pytest.approx(riqueza.cobertura(AMOSTRA))
    assert np.allclose(p[8:], (1 - riqueza.cobertura(AMOSTRA)) / f0)


def test_bootstrap_devolve_um_resumo_por_replica():
    rng = np.random.default_rng(3)
    rep = riqueza.bootstrap_resumos(AMOSTRA, 50, rng)
    assert all(v.shape == (50,) for v in rep.values())
    assert np.all(rep["n"] == 23)
    assert np.all(rep["s"] <= 8 + 4)
    inf, sup = riqueza.intervalo_bootstrap(3.0, np.array([2.0, 3.0, 4.0]))
    assert inf == pytest.approx(3 - 1.959963984540054) and sup == pytest.approx(3 + 1.959963984540054)
    assert riqueza.intervalo_bootstrap(0.5, np.array([0.0, 2.0]))[0] == 0  # piso em zero


# --- Comunidades simuladas de riqueza conhecida -------------------------------------------------


def _amostra(p: np.ndarray, n: int, semente: int) -> np.ndarray:
    sorteio = np.random.default_rng(semente).multinomial(n, p)
    return sorteio


def test_comunidade_homogenea_bem_amostrada_o_chao1_acerta():
    p = np.full(200, 1 / 200)
    x = _amostra(p, 600, 11)
    x = x[x > 0]
    inf, sup = riqueza.intervalo_chao1(x)
    assert riqueza.chao1(x) == pytest.approx(200, rel=0.05)
    assert inf <= 200 <= sup
    assert riqueza.ace(x) == pytest.approx(200, rel=0.05)


def test_caso_em_que_os_estimadores_falham_amostra_pequena_e_muitas_raras():
    # 2.000 espécies com abundância muito desigual e só 300 registros: todos os estimadores ficam
    # muito abaixo da verdade, e o intervalo do Chao1 não a contém. É o limite do método.
    p = np.random.default_rng(5).lognormal(0, 2.5, 2000)
    p /= p.sum()
    x = _amostra(p, 300, 12)
    x = x[x > 0]
    assert riqueza.chao1(x) < 0.5 * 2000
    assert riqueza.ace(x) < 0.5 * 2000
    assert riqueza.jackknife1(x) < 0.5 * 2000
    assert riqueza.intervalo_chao1(x)[1] < 2000
    assert riqueza.chao1(x) > x.size  # ainda assim corrige na direção certa


def test_a_previsao_de_curto_prazo_funciona_mesmo_quando_a_riqueza_total_falha():
    # Mesma comunidade difícil: o Chao1 erra a riqueza, mas as espécies novas nos próximos mil
    # registros (valor esperado exato, com as abundâncias conhecidas) saem perto do previsto.
    p = np.random.default_rng(5).lognormal(0, 2.5, 2000)
    p /= p.sum()
    previstas, verdadeiras = [], []
    for semente in range(20):
        sorteio = _amostra(p, 3000, 100 + semente)
        previstas.append(riqueza.novas_por_mil(sorteio[sorteio > 0]))
        verdadeiras.append((1 - (1 - p[sorteio == 0]) ** 1000).sum())
    assert np.mean(previstas) == pytest.approx(np.mean(verdadeiras), rel=0.15)


def test_cobertura_estimada_acompanha_a_cobertura_real():
    p = np.random.default_rng(7).lognormal(0, 1.5, 1000)
    p /= p.sum()
    estimada, real = [], []
    for semente in range(30):
        sorteio = _amostra(p, 2000, 200 + semente)
        estimada.append(riqueza.cobertura(sorteio[sorteio > 0]))
        real.append(p[sorteio > 0].sum())
    assert np.mean(estimada) == pytest.approx(np.mean(real), abs=0.01)
