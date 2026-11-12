"""Roda a análise completa a partir do extrato em data/ e grava reports/resultados.json, as figuras
e os dois CSVs reutilizáveis. Não usa rede.

Uso: uv run python scripts/rodar_analise.py [pasta_dos_dados] [pasta_de_saida]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from oceano_lacunas import analise, dados, graficos, site


def _registros(tabela: pd.DataFrame) -> list[dict]:
    return json.loads(tabela.to_json(orient="records", force_ascii=False, double_precision=4))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = time.time()
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("reports")
    figuras = saida / "figuras"
    figuras.mkdir(parents=True, exist_ok=True)

    d = dados.carregar(pasta)
    coleta = d["coleta"]
    unid = analise.montar_unidades(d["celulas"], d["unidades"])
    contagens = dados.frequencias_da_unidade(d["frequencias"], "todos")
    antes = dados.frequencias_da_unidade(d["frequencias"], "ate_corte")
    novas = dados.frequencias_da_unidade(d["frequencias"], "novas_depois_corte")

    # Uma semente por etapa: mudar uma etapa não altera os sorteios das outras.
    rng = {nome: np.random.default_rng([analise.SEMENTE, i]) for i, nome in enumerate(("estimar", "validar", "avaliar", "simular"))}

    esforco = analise.resumo_do_esforco(unid, d["celulas"], coleta)
    curvas = analise.curvas_de_lorenz(unid, d["celulas"])
    aval = analise.estimar(unid, contagens, rng["estimar"])
    completude = analise.resumo_da_completude(aval)
    rankings = analise.comparar_rankings(aval)
    val = analise.tabela_de_validacao(unid, antes, novas, rng["validar"])
    avaliacao = analise.avaliar_validacao(val, rng["avaliar"])
    vieses = analise.vieses(unid, aval)
    sim = analise.simular(rng["simular"])
    prioritarias = analise.celulas_prioritarias(aval)
    lacunas = analise.lacunas(unid)

    prioritarias.to_csv(saida / "celulas_prioritarias.csv", index=False, encoding="utf-8")
    lacunas.to_csv(saida / "lacunas_sem_inventario.csv", index=False, encoding="utf-8")

    desenhos = {
        "mapa_do_esforco": graficos.mapa_do_esforco(unid, d["costa"], esforco),
        "lorenz_do_esforco": graficos.lorenz(curvas, esforco),
        "simulacao_dos_estimadores": graficos.simulacao(sim),
        "mapa_de_prioridades": graficos.mapa_de_prioridades(unid, aval, d["costa"], esforco),
        "previsto_x_realizado": graficos.previsto_x_realizado(val, avaliacao),
        "rankings_na_validacao": graficos.rankings_na_validacao(avaliacao),
    }
    for nome, figura in desenhos.items():
        figura.savefig(figuras / f"{nome}.png")
        plt.close(figura)

    colunas_topo = [
        "posto", "celula", "rotulo", "faixa", "registros_especie", "especies", "chao1", "chao1_inf", "chao1_sup",
        "completude", "completude_inf", "completude_sup", "cobertura", "novas_por_mil", "novas_por_mil_inf",
        "novas_por_mil_sup", "novas_por_mil_ace", "posto_ace", "posto_menos_registros", "posto_mais_especies",
        "fracao_maior_conjunto", "maior_conjunto_titulo", "fracao_acima_de_especie", "fracao_oceano",
        "alerta_conjunto_dominante", "posto_sem_alerta",
    ]  # fmt: skip
    mais_amostradas = aval.sort_values("registros_especie", ascending=False).head(5)
    resultados = {
        "coleta": {
            "coletado_em": coleta["coletado_em"],
            "coleta_iniciada_em": coleta["coleta_iniciada_em"],
            "fonte": "OBIS, API v3 (https://api.obis.org/v3): /checklist, /facet e /statistics",
            "relevo": coleta["relevo"],
            "costa": coleta["costa"],
            "grade": coleta["grade"],
            "faixas": coleta["faixas"],
            "ano_de_corte": coleta["ano_de_corte"],
        },
        "parametros": {
            "semente": analise.SEMENTE,
            "min_registros_de_especie": analise.MIN_REGISTROS,
            "registros_adicionais": analise.EXTRA,
            "replicas_de_bootstrap": analise.REPETICOES,
            "area_minima_km2": analise.AREA_MINIMA_KM2,
            "min_registros_posteriores": analise.MIN_POSTERIORES,
            "tamanho_do_topo": analise.TOPO,
        },
        "esforco": esforco,
        "curvas_de_lorenz": curvas,
        "completude": completude,
        "rankings": rankings,
        "topo_do_ranking": _registros(aval.head(analise.TOPO)[colunas_topo]),
        "topo_sem_alerta": _registros(aval[~aval["alerta_conjunto_dominante"]].head(analise.TOPO)[colunas_topo]),
        "mais_amostradas": _registros(mais_amostradas[colunas_topo]),
        "validacao": avaliacao,
        "validacao_por_unidade": _registros(val),
        "vieses": vieses,
        "simulacao": _registros(sim),
    }
    resultados["para_o_site"] = site.bloco(resultados)
    resultados["tempo_de_execucao_s"] = round(time.time() - inicio, 1)
    (saida / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print(json.dumps({k: resultados[k] for k in ("esforco", "completude", "rankings", "validacao", "vieses")}, indent=1, ensure_ascii=False, default=float))
    print(aval.head(analise.TOPO)[colunas_topo[:20]].to_string())
    print(sim.to_string())
    print(f"Gravado em {saida} em {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
