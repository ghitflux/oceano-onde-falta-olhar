"""O bloco do site obedece às regras do portfólio e muda de frase conforme o desfecho da validação."""

from __future__ import annotations

from oceano_lacunas import dados, site


def _resultados(vantagem: float, vantagem_inf: float) -> dict:
    faixa = {
        "unidades": 100, "unidades_sem_registro": 30, "unidades_insuficientes": 40,
        "fracao_da_area_sem_registro": 0.3, "fracao_da_area_sem_inventario": 0.7,
    }  # fmt: skip
    return {
        "coleta": {"coletado_em": "2026-11-12T08:00+00:00"},
        "esforco": {
            "por_faixa": {f: dict(faixa) for f in dados.ID_FAIXAS},
            "obis_inteiro": {"registros": 259_198_986, "especies": 168_316},
        },
        "validacao": {
            "ano_de_corte": 2010,
            "regras": {
                "retorno (Chao1)": {"spearman": 0.45},
                "menos registros": {"spearman": 0.45 - vantagem, "vantagem_do_retorno_chao1": vantagem, "vantagem_inf": vantagem_inf},
                "retorno (Good-Turing)": {"spearman": 0.46, "vantagem_inf": -0.02, "vantagem_sup": 0.01},
            },
            "calibracao_por_mil": {"razao_mediana_realizado_previsto": 3.9},
        },
    }


def test_bloco_do_site_segue_as_regras_do_portfolio():
    b = site.bloco(_resultados(0.08, -0.1))
    for chave in ("numero_chave", "pergunta", "resultado", "detalhe", "dados"):
        assert set(b[chave]) == {"pt", "en", "es"}
    assert all(len(v) <= 12 for v in b["numero_chave"].values())
    assert b["numero_chave"]["pt"] == "70% sem dado"
    g = b["grafico"]
    assert g["tipo"] == "barras" and g["formato_y"] == "percentual"
    assert len(g["series"]) <= 4
    for serie in g["series"]:
        assert serie["papel"] in {"principal", "base", "alternativa", "neutro"}
        assert len(serie["pontos"]) == 4
        assert all(0 <= v <= 1 for _, v in serie["pontos"])
        assert all(len(serie["rotulos"][i]) == 4 for i in ("pt", "en", "es"))
    assert "0,45" in b["resultado"]["pt"] and "0.45" in b["resultado"]["en"]
    assert "3,9" in b["detalhe"]["es"] and "3.9" in b["detalhe"]["en"]
    assert "12/11/2026" in b["dados"]["pt"] and "2026-11-12" in b["dados"]["en"]


def test_a_frase_da_comparacao_segue_o_intervalo_e_nao_o_desejo():
    venceu = site.bloco(_resultados(0.2, 0.05))["resultado"]["pt"]
    empatou = site.bloco(_resultados(0.08, -0.1))["resultado"]["pt"]
    perdeu = site.bloco(_resultados(-0.05, -0.2))["resultado"]["pt"]
    assert "acima da regra simples" in venceu
    assert "cabe no acaso" in empatou
    assert "igual ou melhor" in perdeu
    assert "empatado com a conta de uma linha" in venceu
