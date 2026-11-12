"""Figuras do estudo. A cor segue a entidade: azul é o método (retorno esperado) e a rampa azul é
magnitude; laranja é a linha de base ingênua e também o vazio (onde não há registro); verde-água é
o estimador alternativo; cinza é referência."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from . import dados
from .analise import ZONAS
from .estilo import (
    APAGADO,
    AQUA,
    AZUL,
    EIXO,
    ESTILO,
    GRADE,
    LARANJA,
    RAMPA_AZUL,
    SERIES,
    SUPERFICIE,
    TINTA,
    TINTA_SECUNDARIA,
    milhar,
    numero,
    percentual,
)

RAMPA = LinearSegmentedColormap.from_list("rampa_azul", ["#dfeafa"] + RAMPA_AZUL)
VAZIO = "#f6b79b"  # laranja claro: água sem nenhum registro
INSUFICIENTE = "#dcdbd5"  # cinza: há registro, mas pouco para estimar
COR_FAIXA = dict(zip(dados.ID_FAIXAS, [RAMPA_AZUL[0], RAMPA_AZUL[2], RAMPA_AZUL[3], RAMPA_AZUL[4]]))


def _titulos(fig: Figure, titulo: str, subtitulo: str, y: float = 0.965, passo: float = 0.05) -> None:
    fig.text(0.02, y, titulo, fontsize=13, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, y - passo, subtitulo, fontsize=9.5, color=TINTA_SECUNDARIA, va="top")


def _matriz(tabela: pd.DataFrame, coluna: str) -> np.ndarray:
    """Valores de uma faixa na grade (latitude x longitude), NaN onde não há unidade."""
    lats = np.arange(dados.LAT_MIN, dados.LAT_MAX, dados.PASSO)
    lons = np.arange(-180, 180, dados.PASSO)
    m = np.full((lats.size, lons.size), np.nan)
    i = ((tabela["lat_sul"] - dados.LAT_MIN) // dados.PASSO).to_numpy(int)
    j = ((tabela["lon_oeste"] + 180) // dados.PASSO).to_numpy(int)
    m[i, j] = tabela[coluna].to_numpy(float)
    return m


def _painel_de_mapa(ax, costa, titulo: str) -> None:
    for linha in costa:
        ax.plot(linha[:, 0], linha[:, 1], color=TINTA_SECUNDARIA, linewidth=0.45, zorder=5)
    ax.set_xlim(-180, 180)
    ax.set_ylim(dados.LAT_MIN, dados.LAT_MAX)
    ax.set_aspect("equal")
    ax.grid(visible=False)
    ax.set_xticks([])
    ax.set_yticks([-60, -30, 0, 30, 60], ["60°S", "30°S", "0°", "30°N", "60°N"], fontsize=7.5)
    ax.axhline(0, color=EIXO, linewidth=0.6, zorder=4)
    ax.set_title(titulo, fontsize=9.5, color=TINTA_SECUNDARIA, loc="left", pad=4)
    for lado in ax.spines.values():
        lado.set_visible(False)


def _mapas(unid: pd.DataFrame, costa, coluna: str, norma, titulo: str, subtitulo: str, rotulo_barra: str, com_insuficiente: bool) -> Figure:
    bordas_x = np.arange(-180, 181, dados.PASSO)
    bordas_y = np.arange(dados.LAT_MIN, dados.LAT_MAX + 1, dados.PASSO)
    with plt.rc_context(ESTILO):
        fig, eixos = plt.subplots(2, 2, figsize=(9.4, 6.5), dpi=160)
        fig.subplots_adjust(top=0.83, left=0.055, right=0.985, bottom=0.115, wspace=0.08, hspace=0.16)
        _titulos(fig, titulo, subtitulo)
        malha = None
        for ax, faixa in zip(eixos.ravel(), dados.ID_FAIXAS):
            u = unid[(unid["faixa"] == faixa) & unid["tem_agua"]]
            vazio = _matriz(u[u["zona"] == ZONAS[0]].assign(v=1.0), "v")
            ax.pcolormesh(bordas_x, bordas_y, vazio, cmap=LinearSegmentedColormap.from_list("v", [VAZIO, VAZIO]), zorder=2)
            if com_insuficiente:
                pouco = _matriz(u[u["zona"] == ZONAS[1]].assign(v=1.0), "v")
                ax.pcolormesh(bordas_x, bordas_y, pouco, cmap=LinearSegmentedColormap.from_list("i", [INSUFICIENTE, INSUFICIENTE]), zorder=2)
                valores = _matriz(u[u["zona"] == ZONAS[2]], coluna)
            else:
                valores = _matriz(u[u["registros"] > 0], coluna)
            malha = ax.pcolormesh(bordas_x, bordas_y, np.ma.masked_invalid(valores), cmap=RAMPA, norm=norma, zorder=3)
            if com_insuficiente:
                contagem = f"{int((u['zona'] == ZONAS[2]).sum())} de {len(u)} células com dado para estimar"
            else:
                contagem = f"{int((u['zona'] == ZONAS[0]).sum())} de {len(u)} células sem registro"
            _painel_de_mapa(ax, costa, f"{dados.ROTULO_FAIXA[faixa].capitalize()}: {contagem}")
        barra = fig.add_axes([0.40, 0.055, 0.34, 0.016])
        cb = fig.colorbar(malha, cax=barra, orientation="horizontal")
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=8, length=2)
        cb.ax.xaxis.set_major_formatter(lambda v, _: milhar(v) if v >= 1 else numero(v, 2 if v < 0.1 else 1))
        fig.text(0.39, 0.063, rotulo_barra, fontsize=8.5, color=TINTA_SECUNDARIA, ha="right", va="center")
        marcas = [Patch(facecolor=VAZIO, label="água sem nenhum registro")]
        if com_insuficiente:
            marcas.append(Patch(facecolor=INSUFICIENTE, label="menos de 500 registros de espécie"))
        fig.legend(handles=marcas, loc="lower right", bbox_to_anchor=(0.985, 0.03), fontsize=8.5, ncols=1, handlelength=1.2)
        return fig


def mapa_do_esforco(unid: pd.DataFrame, costa, resumo: dict) -> Figure:
    """Quatro mapas, um por faixa de profundidade: registros por mil km² de oceano."""
    raso, fundo = resumo["por_faixa"]["0-200"], resumo["por_faixa"]["4000+"]
    return _mapas(
        unid, costa, "densidade", LogNorm(vmin=0.01, vmax=10_000),
        f"O esforço cai {milhar(resumo['razao_superficie_fundo'])} vezes da superfície ao fundo, e {percentual(fundo['fracao_da_area_sem_registro'])} da área abaixo de 4.000 m não tem registro algum",
        f"Registros do OBIS com profundidade informada, por mil km² de oceano, em células de 10° x 10°. De 0 a 200 m: {milhar(raso['registros_por_mil_km2'])} por mil km²; abaixo de 4.000 m: {numero(fundo['registros_por_mil_km2'], 1)}.",
        "registros por mil km² (escala log)", com_insuficiente=False,
    )  # fmt: skip


def mapa_de_prioridades(unid: pd.DataFrame, aval: pd.DataFrame, costa, resumo: dict) -> Figure:
    """Os mesmos quatro mapas com a resposta à decisão: espécies novas esperadas por mil registros."""
    junto = unid.merge(aval[["celula", "faixa", "novas_por_mil"]], on=["celula", "faixa"], how="left")
    junto["novas_por_mil"] = junto["novas_por_mil"].clip(lower=1)
    sem = sum(f["unidades_sem_registro"] + f["unidades_insuficientes"] for f in resumo["por_faixa"].values())
    total = sum(f["unidades"] for f in resumo["por_faixa"].values())
    return _mapas(
        junto, costa, "novas_por_mil", LogNorm(vmin=1, vmax=500),
        f"Em {milhar(sem)} das {milhar(total)} combinações de célula e profundidade não há dado nem para estimar",
        "Onde há dado (azul): espécies novas para a célula esperadas a cada mil registros adicionais. Quanto mais escuro, maior o retorno.",
        "espécies novas por mil registros (escala log)", com_insuficiente=True,
    )  # fmt: skip


def lorenz(curvas: dict, resumo: dict) -> Figure:
    """Curva de Lorenz do esforço por faixa de profundidade."""
    d = resumo["desigualdade_celulas"]
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=160)
        fig.subplots_adjust(top=0.80, left=0.09, right=0.74, bottom=0.12)
        _titulos(
            fig,
            f"Metade dos registros do OBIS vem de {percentual(d['fracao_da_area_com_metade_dos_registros'], 1)} da área do oceano",
            f"Curva de Lorenz: células de 10° x 10° da menos para a mais amostrada. A metade menos amostrada do oceano guarda {percentual(d['fracao_dos_registros_na_metade_menos_amostrada'], 1)} dos registros.",
            y=0.955, passo=0.06,
        )  # fmt: skip
        ax.plot([0, 1], [0, 1], color=APAGADO, linewidth=1)
        ax.annotate("esforço uniforme", (0.5, 0.5), xytext=(-8, 8), textcoords="offset points", color=TINTA_SECUNDARIA, fontsize=8.5, ha="right")
        for faixa in dados.ID_FAIXAS:
            pontos = np.asarray(curvas[faixa])
            ax.plot(pontos[:, 0], pontos[:, 1], color=COR_FAIXA[faixa], linewidth=1.6)
        pontos = np.asarray(curvas["todas"])
        ax.plot(pontos[:, 0], pontos[:, 1], color=TINTA, linewidth=2.2)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.xaxis.set_major_formatter(lambda v, _: percentual(v))
        ax.yaxis.set_major_formatter(lambda v, _: percentual(v))
        ax.set_xlabel("Fração acumulada da área de oceano")
        ax.set_ylabel("Fração acumulada dos registros")
        linhas = [f"todos os registros: Gini {numero(d['gini'])}"]
        linhas += [f"{dados.ROTULO_FAIXA[f]}: Gini {numero(resumo['por_faixa'][f]['gini'])}" for f in dados.ID_FAIXAS]
        marcas = [plt.Line2D([], [], color=TINTA, linewidth=2.2)] + [plt.Line2D([], [], color=COR_FAIXA[f], linewidth=1.6) for f in dados.ID_FAIXAS]
        fig.legend(
            handles=marcas, labels=linhas, loc="center left", bbox_to_anchor=(0.69, 0.45), fontsize=9,
            title="Registros considerados", title_fontsize=9, alignment="left",
        )  # fmt: skip
        fig.text(0.70, 0.27, "As faixas só contam registros\ncom profundidade informada.", fontsize=8.5, color=TINTA_SECUNDARIA, va="top")
        return fig


def simulacao(sim: pd.DataFrame) -> Figure:
    """Estimadores sobre a riqueza verdadeira em comunidades simuladas, por tamanho de amostra."""
    series = [
        ("observada_sobre_real", "espécies observadas", APAGADO),
        ("chao1_sobre_real", "Chao1", AZUL),
        ("ace_sobre_real", "ACE", AQUA),
        ("jackknife1_sobre_real", "jackknife", SERIES[3]),
    ]
    with plt.rc_context(ESTILO):
        fig, eixos = plt.subplots(1, 2, figsize=(9.0, 4.6), dpi=160, sharey=True)
        fig.subplots_adjust(top=0.74, left=0.08, right=0.98, bottom=0.21, wspace=0.07)
        _titulos(
            fig,
            "Com muitas espécies raras e pouca amostra, todo estimador fica muito abaixo da riqueza real",
            "Comunidades simuladas com 2.000 espécies. Eixo vertical: estimativa dividida pela riqueza verdadeira (100% = acerto).",
            y=0.96, passo=0.065,
        )  # fmt: skip
        nomes = {"equilibrada": "Comunidade equilibrada", "muitas raras": "Comunidade com muitas espécies raras"}
        for ax, (comunidade, nome) in zip(eixos, nomes.items()):
            g = sim[sim["comunidade"] == comunidade]
            ax.axhline(1, color=TINTA_SECUNDARIA, linewidth=1)
            for coluna, _, cor in series:
                ax.plot(g["registros"], g[coluna], color=cor, marker="o", markersize=6)
            ax.set_xscale("log")
            ax.set_title(nome, fontsize=9.5, color=TINTA_SECUNDARIA, loc="left", pad=6)
            ax.set_xlabel("Registros na amostra (escala log)")
            ax.xaxis.set_major_formatter(lambda v, _: milhar(v))
            ax.yaxis.set_major_formatter(lambda v, _: percentual(v))
            ax.set_ylim(0, 1.3)
        eixos[0].set_ylabel("Estimativa / riqueza verdadeira")
        fig.legend(
            handles=[plt.Line2D([], [], color=c, marker="o", markersize=6, linewidth=2) for _, _, c in series],
            labels=[n for _, n, _ in series], loc="lower center", ncols=4, fontsize=9, bbox_to_anchor=(0.5, 0.0),
        )  # fmt: skip
        return fig


def previsto_x_realizado(val: pd.DataFrame, avaliacao: dict) -> Figure:
    """Dispersão log-log: previsto com o que se sabia até o corte contra o realizado depois."""
    c = avaliacao["calibracao_por_mil"]
    r = avaliacao["regras"]["retorno (Chao1)"]
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=160)
        fig.subplots_adjust(top=0.78, left=0.11, right=0.97, bottom=0.12)
        razao = numero(c["razao_mediana_realizado_previsto"], 1)
        if r["spearman_inf"] > 0:
            titulo = f"A ordem se aproveita (correlação {numero(r['spearman'])}); o tamanho não: apareceu {razao} vezes o previsto"
        else:
            titulo = f"Nem a ordem (correlação {numero(r['spearman'])}) nem o tamanho se confirmam: apareceu {razao} vezes o previsto"
        _titulos(
            fig,
            titulo,
            f"Cada ponto é uma célula numa faixa de profundidade ({avaliacao['unidades']} ao todo). Previsão feita só com registros até {avaliacao['ano_de_corte']}.\nEscalas logarítmicas; valores abaixo de 0,3 aparecem em 0,3.",
            y=0.955, passo=0.055,
        )  # fmt: skip
        piso = 0.3
        x, y = val["previsto"].clip(lower=piso), val["realizado"].clip(lower=piso)
        limite = float(max(x.max(), y.max()) * 1.6)
        ax.plot([piso, limite], [piso, limite], color=APAGADO, linewidth=1)
        ax.annotate("previsto = realizado", (limite / 1.7, limite / 1.7), xytext=(-6, 4), textcoords="offset points", ha="right", fontsize=8.5, color=TINTA_SECUNDARIA)
        ax.scatter(x, y, s=26, color=AZUL, edgecolor=SUPERFICIE, linewidth=0.8, alpha=0.85, zorder=3)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(piso, limite)
        ax.set_ylim(piso, limite)
        ax.grid(axis="x", visible=True)
        for eixo in (ax.xaxis, ax.yaxis):
            eixo.set_major_formatter(lambda v, _: milhar(v) if v >= 1 else numero(v, 1))
        ax.set_xlabel(f"Previsto: espécies novas por mil registros, com dados até {avaliacao['ano_de_corte']}")
        ax.set_ylabel(f"Realizado: espécies novas em mil registros de {avaliacao['ano_de_corte'] + 1} em diante")
        return fig


def rankings_na_validacao(avaliacao: dict) -> Figure:
    """Correlação de cada regra de prioridade com o que de fato apareceu depois do corte."""
    cores = {
        "retorno (Chao1)": AZUL,
        "retorno (ACE)": AQUA,
        "retorno (Good-Turing)": AQUA,
        "menos registros": LARANJA,
        "mais espécies registradas": LARANJA,
    }
    nomes = {
        "retorno (Chao1)": "Retorno esperado (extrapolação com Chao1)",
        "retorno (ACE)": "Retorno esperado (extrapolação com ACE)",
        "retorno (Good-Turing)": "Singletons por registro (Good-Turing)",
        "menos registros": "Ir aonde há menos registros",
        "mais espécies registradas": "Ir aonde há mais espécies registradas",
    }
    regras = avaliacao["regras"]
    base = regras["menos registros"]
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=160)
        fig.subplots_adjust(top=0.72, left=0.40, right=0.95, bottom=0.15)
        par = f"{numero(regras['retorno (Chao1)']['spearman'])} contra {numero(base['spearman'])}"
        if base["vantagem_inf"] > 0:
            titulo = f"O retorno esperado ordena melhor que ir aonde há menos registros: {par}"
        elif base["vantagem_do_retorno_chao1"] > 0:
            titulo = f"O retorno esperado ordena um pouco melhor que “menos registros”, e a diferença cabe no acaso: {par}"
        else:
            titulo = f"Ir aonde há menos registros ordena tão bem quanto o retorno esperado: {par}"
        gt = regras["retorno (Good-Turing)"]
        empate = gt["vantagem_inf"] <= 0 <= gt["vantagem_sup"]
        nota = "A extrapolação não supera a conta de uma linha (singletons por registro)." if empate else ""
        _titulos(
            fig,
            titulo,
            f"Correlação de postos entre cada regra, aplicada aos dados até {avaliacao['ano_de_corte']}, e as espécies novas realizadas depois. Traço: intervalo de 95%.\n{nota}",
            y=0.95, passo=0.07,
        )  # fmt: skip
        y = np.arange(len(regras))
        for i, (nome, r) in enumerate(regras.items()):
            ax.barh(i, r["spearman"], height=0.5, color=cores[nome], zorder=3)
            ax.plot([r["spearman_inf"], r["spearman_sup"]], [i, i], color=TINTA, linewidth=1.2, zorder=4)
            ax.annotate(numero(r["spearman"]), (max(r["spearman_sup"], 0), i), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=TINTA)
        ax.axvline(0, color=TINTA_SECUNDARIA, linewidth=0.8)
        ax.set_yticks(y, [nomes[n] for n in regras], fontsize=9)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_xlim(min(-0.2, min(r["spearman_inf"] for r in regras.values()) - 0.05), 1.0)
        ax.xaxis.set_major_formatter(lambda v, _: numero(v, 1))
        ax.set_xlabel("Correlação de Spearman com o realizado")
        return fig


__all__ = ["mapa_do_esforco", "mapa_de_prioridades", "lorenz", "simulacao", "previsto_x_realizado", "rankings_na_validacao", "GRADE"]
