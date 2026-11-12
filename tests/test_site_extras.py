"""Os gráficos adicionais do site: forma, limites, três idiomas e valores vindos dos resultados."""

from __future__ import annotations

import numpy as np

from oceano_lacunas import dados, site, site_extras

IDIOMAS = {"pt", "en", "es"}
PAPEIS = {"principal", "base", "alternativa", "neutro"}
FORMATOS = {"numero", "percentual", "moeda", "data"}


def _resultados(vantagem_inf: float = 0.06, spearman_inf: float = 0.39) -> dict:
    rng = np.random.default_rng(0)
    previsto = rng.gamma(1.5, 10.0, 60)
    grade = np.linspace(0, 1, 101)
    faixa = {
        "unidades": 100, "unidades_sem_registro": 30, "unidades_insuficientes": 40,
        "fracao_da_area_sem_registro": 0.3, "fracao_da_area_sem_inventario": 0.7, "registros_por_mil_km2": 292.0,
    }  # fmt: skip
    regra = {"spearman": 0.3, "spearman_inf": 0.2, "spearman_sup": 0.4, "vantagem_do_retorno_chao1": 0.1, "vantagem_inf": 0.01, "vantagem_sup": 0.2}
    return {
        "coleta": {"coletado_em": "2026-11-12T08:00+00:00"},
        "esforco": {
            "por_faixa": {f: dict(faixa, registros_por_mil_km2=292.0 / (10**k)) for k, f in enumerate(dados.ID_FAIXAS)},
            "por_hemisferio": {h: {f: m * 100.0 / (k + 1) for k, f in enumerate(dados.ID_FAIXAS)} for h, m in (("Norte", 2.5), ("Sul", 1.0))},
            "obis_inteiro": {"registros": 259_198_986, "especies": 168_316},
            "razao_superficie_fundo": 83.3,
            "razao_norte_sul_superficie": 2.46,
            "desigualdade_celulas": {
                "gini": 0.9013, "fracao_da_area_com_metade_dos_registros": 0.0124,
                "fracao_dos_registros_na_metade_menos_amostrada": 0.0122,
            },  # fmt: skip
        },
        "curvas_de_lorenz": {k: [[float(x), float(x**9)] for x in grade] for k in ("todas", *dados.ID_FAIXAS)},
        "validacao": {
            "ano_de_corte": 2010,
            "unidades": 60,
            "regras": {
                "retorno (Chao1)": {"spearman": 0.49, "spearman_inf": spearman_inf, "spearman_sup": 0.58},
                "retorno (ACE)": dict(regra, spearman=0.488),
                "retorno (Good-Turing)": dict(regra, spearman=0.493, vantagem_inf=-0.02, vantagem_sup=0.01),
                "menos registros": dict(regra, spearman=0.353, vantagem_do_retorno_chao1=0.137, vantagem_inf=vantagem_inf),
                "mais espécies registradas": dict(regra, spearman=0.013),
            },
            "calibracao_por_mil": {"razao_mediana_realizado_previsto": 3.38, "fracao_dentro_do_intervalo": 0.06},
        },
        "validacao_por_unidade": [{"previsto": float(p), "realizado": float(3 * p + rng.normal())} for p in previsto],
        "simulacao": [
            {"comunidade": c, "registros": n, "chao1_sobre_real": 0.1 + 0.1 * k, "observada_sobre_real": 0.05 + 0.1 * k, "previstas_sobre_verdadeiras": 0.6 + 0.06 * k}
            for c in ("equilibrada", "muitas raras")
            for k, n in enumerate([100, 300, 1000, 3000, 10_000, 30_000, 100_000])
        ],
    }


def test_graficos_extras_tem_a_forma_que_o_site_espera():
    extras = site.bloco(_resultados())["graficos_extras"]
    assert 3 <= len(extras) <= 5
    for g in extras:
        assert g["tipo"] in {"linhas", "barras", "pontos"}
        for campo in ("titulo", "leitura", "eixo_x", "eixo_y"):
            assert set(g[campo]) == IDIOMAS
            assert all(isinstance(v, str) and v.strip() for v in g[campo].values())
        assert all(len(t) <= 90 for t in g["titulo"].values()), g["titulo"]
        assert g["formato_x"] in FORMATOS and g["formato_y"] in FORMATOS
        assert 1 <= len(g["series"]) <= 4
        for serie in g["series"]:
            assert set(serie["nome"]) == IDIOMAS
            assert serie["papel"] in PAPEIS
            limite = 300 if g["tipo"] == "pontos" else 80
            assert 1 <= len(serie["pontos"]) <= limite
            for x, y in serie["pontos"]:
                assert isinstance(y, (int, float)) and np.isfinite(y)
                assert isinstance(x, str) if g["tipo"] == "barras" else isinstance(x, (int, float))
            if g["tipo"] == "barras":
                assert set(serie["rotulos"]) == IDIOMAS
                assert all(len(v) == len(serie["pontos"]) for v in serie["rotulos"].values())
                assert [p[0] for p in serie["pontos"]] == serie["rotulos"]["pt"]
        if "faixa" in g:
            assert g["tipo"] == "linhas"
            n = len(g["series"][g["faixa"]["serie"]]["pontos"])
            assert len(g["faixa"]["inferior"]) == len(g["faixa"]["superior"]) == n
            assert all(a[1] <= b[1] for a, b in zip(g["faixa"]["inferior"], g["faixa"]["superior"]))


def test_o_bloco_principal_continua_igual_com_os_extras():
    r = _resultados()
    completo = site.bloco(r)
    assert {k: v for k, v in completo.items() if k != "graficos_extras"} == site.bloco_principal(r)


def test_os_valores_dos_extras_saem_dos_resultados():
    r = _resultados()
    ranking, calibracao, esforco, lorenz, simulacao = site_extras.graficos(r)
    assert dict(ranking["series"][0]["pontos"])["Menos registros"] == 0.353
    assert "0,49 contra 0,35" in ranking["titulo"]["pt"] and "0.49 vs 0.35" in ranking["titulo"]["en"]
    assert "3,4" in calibracao["titulo"]["pt"] and "3.4" in calibracao["titulo"]["en"]
    assert len(calibracao["series"][0]["pontos"]) == site_extras.GRUPOS_DA_CALIBRACAO
    assert all(x == y for x, y in calibracao["series"][1]["pontos"])  # a diagonal
    xs = [p[0] for p in calibracao["series"][0]["pontos"]]
    assert xs == sorted(xs)
    assert esforco["series"][0]["pontos"][0][1] == 250.0 and esforco["series"][1]["pontos"][3][1] == 25.0
    assert "83" in esforco["titulo"]["pt"] and "2,5" in esforco["titulo"]["pt"]
    assert "1,2%" in lorenz["titulo"]["pt"] and "1.2%" in lorenz["titulo"]["en"]
    assert lorenz["series"][0]["pontos"][0] == [0.0, 0.0] and lorenz["series"][0]["pontos"][-1] == [1.0, 1.0]
    assert len(simulacao["series"][0]["pontos"]) == 7
    assert simulacao["series"][0]["rotulos"]["en"][-1] == "100,000" and simulacao["series"][0]["rotulos"]["pt"][-1] == "100.000"


def test_os_titulos_dos_extras_seguem_o_intervalo():
    empate = site_extras.rankings(_resultados(vantagem_inf=-0.05))["titulo"]["pt"]
    assert "ordenam parecido" in empate
    sem_ordem = site_extras.calibracao(_resultados(spearman_inf=-0.1))["titulo"]["pt"]
    assert "Nem a ordem" in sem_ordem
