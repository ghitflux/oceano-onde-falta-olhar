"""Estimadores não paramétricos de riqueza, cobertura da amostra, rarefação e extrapolação.

Tudo aqui recebe um vetor `x` com o número de registros de cada espécie observada (inteiros > 0) e
usa só a distribuição de frequência: f1 = espécies com um registro (singletons), f2 = com dois
(doubletons), e assim por diante. A ideia comum a todos: as espécies raras da amostra carregam a
informação sobre as espécies que ainda não apareceram.

Referências (conferidas pelo DOI no Crossref):
- Chao (1984), Scand. J. Statist. 11:265-270: o limite inferior Chao1.
- Chao (1987), Biometrics 43:783-791, doi:10.2307/2531532: variância e intervalo log-normal.
- Chao & Lee (1992), JASA 87:210-217, doi:10.1080/01621459.1992.10475194: ACE.
- Burnham & Overton (1978), Biometrika 65:625-633, doi:10.1093/biomet/65.3.625: jackknife.
- Good (1953), Biometrika 40:237-264, doi:10.1093/biomet/40.3-4.237: cobertura (Good-Turing).
- Chao & Jost (2012), Ecology 93:2533-2547, doi:10.1890/11-1952.1: cobertura corrigida e
  padronização por cobertura.
- Hurlbert (1971), Ecology 52:577-586, doi:10.2307/1934145: rarefação.
- Shen, Chao & Lin (2003), Ecology 84:798-804: espécies novas em amostragem adicional.
- Chao et al. (2014), Ecol. Monogr. 84:45-67, doi:10.1890/13-0133.1: extrapolação e bootstrap.

O pressuposto de todos é que os registros são uma amostra aleatória dos indivíduos da comunidade.
Registros de ocorrência não são; o estudo trata isso como limitação e testa a consequência na
validação no tempo.
"""

from __future__ import annotations

import numpy as np
from scipy.special import gammaln

LIMIAR_RARAS = 10  # no ACE, espécie "rara" tem até 10 registros
Z95 = 1.959963984540054


def _vetor(x) -> np.ndarray:
    x = np.asarray(x, dtype=np.int64)
    return x[x > 0]


def resumo(x) -> tuple[int, int, int, int]:
    """(n, S, f1, f2): registros, espécies observadas, singletons e doubletons."""
    x = _vetor(x)
    return int(x.sum()), int(x.size), int((x == 1).sum()), int((x == 2).sum())


# ----------------------------------------------------------------------------------------------
# Riqueza
# ----------------------------------------------------------------------------------------------


def f0_chao1(n, f1, f2):
    """Espécies não vistas pelo Chao1. Aceita escalares ou vetores (usado no bootstrap).

    Com doubletons: (n−1)/n · f1² / (2·f2). Sem doubletons a fórmula dividiria por zero e usa-se a
    forma corrigida: (n−1)/n · f1·(f1−1)/2.
    """
    n, f1, f2 = (np.asarray(v, dtype=float) for v in (n, f1, f2))
    k = np.where(n > 0, (n - 1) / np.maximum(n, 1), 0.0)
    com = k * f1**2 / (2 * np.maximum(f2, 1))
    sem = k * f1 * (f1 - 1) / 2
    return np.where(f2 > 0, com, sem)


def chao1(x) -> float:
    """Riqueza estimada pelo Chao1: observadas + não vistas. É um limite inferior."""
    n, s, f1, f2 = resumo(x)
    return float(s + f0_chao1(n, f1, f2))


def intervalo_chao1(x, z: float = Z95) -> tuple[float, float]:
    """Intervalo de confiança log-normal do Chao1 (Chao, 1987).

    O intervalo é assimétrico e nunca fica abaixo do número de espécies observadas: aplica-se o
    log-normal à parte não vista, T = Chao1 − S.
    """
    n, s, f1, f2 = resumo(x)
    if n == 0:
        return 0.0, 0.0
    k = (n - 1) / n
    estimativa = s + float(f0_chao1(n, f1, f2))
    t = estimativa - s
    if t <= 0:
        return float(s), float(s)
    if f2 > 0:
        r = f1 / f2
        var = f2 * (k * r**2 / 2 + k**2 * r**3 + k**2 * r**4 / 4)
    else:
        var = k * f1 * (f1 - 1) / 2 + k**2 * f1 * (2 * f1 - 1) ** 2 / 4 - k**2 * f1**4 / (4 * estimativa)
    var = max(var, 0.0)
    fator = float(np.exp(z * np.sqrt(np.log(1 + var / t**2))))
    return s + t / fator, s + t * fator


def ace(x, limiar: int = LIMIAR_RARAS) -> float:
    """ACE, estimador por cobertura das espécies raras (Chao & Lee, 1992).

    Separa as espécies em abundantes (mais de `limiar` registros) e raras; estima a cobertura das
    raras, C = 1 − f1/n_raras, e corrige pela heterogeneidade (γ²). Quando todas as raras são
    singletons a cobertura é zero e a fórmula não se aplica: cai-se no Chao1.
    """
    x = _vetor(x)
    raras = x[x <= limiar]
    s_abund, s_raras, n_raras = int((x > limiar).sum()), int(raras.size), int(raras.sum())
    f1 = int((raras == 1).sum())
    if s_raras == 0:
        return float(x.size)
    cobertura_raras = 1 - f1 / n_raras
    if cobertura_raras <= 0 or n_raras < 2:
        return chao1(x)
    soma = float((raras * (raras - 1)).sum())
    gama2 = max(s_raras / cobertura_raras * soma / (n_raras * (n_raras - 1)) - 1, 0.0)
    return float(s_abund + s_raras / cobertura_raras + f1 / cobertura_raras * gama2)


def jackknife1(x) -> float:
    """Jackknife de primeira ordem: S + f1·(n−1)/n (Burnham & Overton, 1978)."""
    n, s, f1, _ = resumo(x)
    return float(s + f1 * (n - 1) / n) if n else 0.0


# ----------------------------------------------------------------------------------------------
# Cobertura
# ----------------------------------------------------------------------------------------------


def _fator_cobertura(n, f1, f2):
    """A = (n−1)·f1 / ((n−1)·f1 + 2·f2), o termo que corrige o Good-Turing (Chao & Jost, 2012)."""
    n, f1, f2 = (np.asarray(v, dtype=float) for v in (n, f1, f2))
    com = (n - 1) * f1 / np.maximum((n - 1) * f1 + 2 * f2, 1e-300)
    sem = (n - 1) * (f1 - 1) / np.maximum((n - 1) * (f1 - 1) + 2, 1e-300)
    return np.where(f2 > 0, com, np.where(f1 > 1, sem, 1.0))


def cobertura_good_turing(x) -> float:
    """Cobertura de Good-Turing: 1 − f1/n. A chance de o próximo registro ser de espécie já vista."""
    n, _, f1, _ = resumo(x)
    return 1 - f1 / n if n else 0.0


def cobertura(x) -> float:
    """Cobertura da amostra com a correção de Chao & Jost (2012): 1 − (f1/n)·A."""
    n, _, f1, f2 = resumo(x)
    if n == 0:
        return 0.0
    if f1 == 0:
        return 1.0
    return float(1 - f1 / n * _fator_cobertura(n, f1, f2))


def cobertura_extrapolada(x, extra: float) -> float:
    """Cobertura esperada depois de `extra` registros adicionais: 1 − (f1/n)·A^(extra+1)."""
    n, _, f1, f2 = resumo(x)
    if n == 0:
        return 0.0
    if f1 == 0:
        return 1.0
    return float(1 - f1 / n * _fator_cobertura(n, f1, f2) ** (extra + 1))


def registros_para_cobertura(x, alvo: float) -> float:
    """Quantos registros adicionais levam a cobertura até `alvo` (0 se já chegou; inf se não chega)."""
    n, _, f1, f2 = resumo(x)
    if n == 0:
        return float("inf")
    if cobertura(x) >= alvo:
        return 0.0
    a = float(_fator_cobertura(n, f1, f2))
    if a >= 1 or a <= 0:
        return float("inf")
    return float(max(np.log((1 - alvo) * n / f1) / np.log(a) - 1, 0.0))


# ----------------------------------------------------------------------------------------------
# Rarefação e extrapolação
# ----------------------------------------------------------------------------------------------


def _log_binomial(a, b):
    return gammaln(a + 1) - gammaln(b + 1) - gammaln(a - b + 1)


def rarefacao(x, m) -> np.ndarray | float:
    """Riqueza esperada numa subamostra de `m` registros sorteados sem reposição (Hurlbert, 1971).

    E[S_m] = S − Σ_k f_k · C(n−k, m)/C(n, m). `m` pode ser escalar ou vetor, com 0 ≤ m ≤ n.
    """
    x = _vetor(x)
    n = int(x.sum())
    ks, fs = np.unique(x, return_counts=True)
    ms = np.atleast_1d(np.asarray(m, dtype=float))
    if np.any(ms > n) or np.any(ms < 0):
        raise ValueError("rarefação só vale para 0 <= m <= n; acima de n use `extrapolacao`")
    saida = np.empty(ms.size)
    for i, mi in enumerate(ms):
        possivel = (n - ks) >= mi
        ausente = np.zeros(ks.size)
        ausente[possivel] = np.exp(_log_binomial(n - ks[possivel], mi) - _log_binomial(n, mi))
        saida[i] = x.size - float((fs * ausente).sum())
    return float(saida[0]) if np.isscalar(m) else saida


def rarefacao_parcial(x_subconjunto, n_total: int, m: float) -> float:
    """Quantas espécies de um subconjunto aparecem, em média, em `m` registros sorteados de um total
    de `n_total` (o subconjunto é parte do total).

    É a mesma conta de Hurlbert restrita a algumas espécies. A validação no tempo usa isto para pôr
    todas as unidades no mesmo esforço: das espécies que só apareceram depois do corte, quantas
    apareceriam em mil registros sorteados entre os posteriores ao corte.
    """
    x = _vetor(x_subconjunto)
    if m > n_total or x.sum() > n_total:
        raise ValueError("m e o subconjunto não podem passar do total")
    ks, fs = np.unique(x, return_counts=True)
    possivel = (n_total - ks) >= m
    ausente = np.zeros(ks.size)
    ausente[possivel] = np.exp(_log_binomial(n_total - ks[possivel], m) - _log_binomial(n_total, m))
    return float(x.size - (fs * ausente).sum())


def cobertura_rarefeita(x, m: float) -> float:
    """Cobertura esperada de uma subamostra de m < n registros (Chao & Jost, 2012).

    C(m) = 1 − Σ_i (x_i/n) · C(n−x_i, m)/C(n−1, m).
    """
    x = _vetor(x)
    n = int(x.sum())
    if m >= n:
        return cobertura(x)
    ks, fs = np.unique(x, return_counts=True)
    possivel = (n - ks) >= m
    termo = np.zeros(ks.size)
    termo[possivel] = np.exp(_log_binomial(n - ks[possivel], m) - _log_binomial(n - 1, m))
    return float(1 - (fs * ks / n * termo).sum())


def novas_esperadas(n, s, f1, f2, extra, f0=None):
    """Espécies novas esperadas em `extra` registros adicionais (Shen, Chao & Lin, 2003).

    novas = f0 · [1 − (1 − f1/(n·f0 + f1))^extra], com f0 = espécies não vistas (por padrão, as do
    Chao1). A curva sobe com inclinação f1/n no começo e satura em f0. Aceita vetores.
    """
    n, f1, f2, extra = (np.asarray(v, dtype=float) for v in (n, f1, f2, extra))
    f0 = f0_chao1(n, f1, f2) if f0 is None else np.asarray(f0, dtype=float)
    base = 1 - f1 / np.maximum(n * f0 + f1, 1e-300)
    return np.where((f0 > 0) & (f1 > 0), f0 * (1 - base**extra), 0.0)


def extrapolacao(x, extra, f0: float | None = None):
    """Riqueza esperada com n + `extra` registros: S observada + espécies novas esperadas.

    A literatura recomenda não confiar além de duas a três vezes o tamanho da amostra.
    """
    n, s, f1, f2 = resumo(x)
    return s + novas_esperadas(n, s, f1, f2, extra, f0)


def novas_por_mil(x, f0: float | None = None, extra: int = 1000) -> float:
    """Espécies novas para a unidade esperadas nos próximos `extra` registros."""
    n, s, f1, f2 = resumo(x)
    return float(novas_esperadas(n, s, f1, f2, extra, f0))


def riqueza_na_cobertura(x, alvo: float, limite_extrapolacao: float = 2.0) -> float:
    """Riqueza padronizada por cobertura (Chao & Jost, 2012): quantas espécies a unidade teria numa
    amostra com cobertura `alvo`.

    Se a amostra já passou do alvo, rarefaz até o tamanho em que a cobertura é `alvo`; se não,
    extrapola. Devolve NaN quando a extrapolação pediria mais de `limite_extrapolacao` vezes o
    tamanho da amostra (ali a conta deixa de ser confiável).
    """
    x = _vetor(x)
    n = int(x.sum())
    if n == 0:
        return float("nan")
    if cobertura(x) >= alvo:
        baixo, alto = 1.0, float(n)
        if cobertura_rarefeita(x, 1) >= alvo:
            return float(rarefacao(x, 1.0))
        for _ in range(60):
            meio = (baixo + alto) / 2
            if cobertura_rarefeita(x, meio) < alvo:
                baixo = meio
            else:
                alto = meio
            if alto - baixo < 0.5:
                break
        return float(rarefacao(x, min((baixo + alto) / 2, n)))
    extra = registros_para_cobertura(x, alvo)
    if not np.isfinite(extra) or extra > limite_extrapolacao * n:
        return float("nan")
    return float(extrapolacao(x, extra))


# ----------------------------------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------------------------------


def comunidade_bootstrap(x) -> np.ndarray:
    """Abundâncias relativas da comunidade de onde o bootstrap sorteia (Chao et al., 2014).

    Sortear da amostra observada ignoraria as espécies não vistas e daria intervalos estreitos
    demais. Aqui a comunidade tem as S espécies observadas, com a frequência encolhida para somar a
    cobertura estimada C, mais f0 (Chao1, arredondado para cima) espécies não vistas que dividem
    por igual a massa restante 1 − C.
    """
    x = _vetor(x)
    n, s, f1, f2 = resumo(x)
    c = cobertura(x)
    f0 = int(np.ceil(float(f0_chao1(n, f1, f2))))
    p = x / n
    if f0 == 0 or c >= 1:
        return p
    peso = p * (1 - p) ** n
    lam = (1 - c) / peso.sum() if peso.sum() > 0 else 0.0
    vistas = p * (1 - lam * (1 - p) ** n)
    probabilidades = np.concatenate([vistas, np.full(f0, (1 - c) / f0)])
    return probabilidades / probabilidades.sum()


def bootstrap_resumos(x, repeticoes: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Sorteia `repeticoes` amostras de n registros da comunidade bootstrap e devolve S, f1 e f2 de
    cada uma (vetores), que bastam para recalcular o Chao1, a cobertura e a extrapolação."""
    n = int(_vetor(x).sum())
    sorteios = rng.multinomial(n, comunidade_bootstrap(x), size=repeticoes)
    return {
        "n": np.full(repeticoes, n, dtype=float),
        "s": (sorteios > 0).sum(axis=1).astype(float),
        "f1": (sorteios == 1).sum(axis=1).astype(float),
        "f2": (sorteios == 2).sum(axis=1).astype(float),
    }


def intervalo_bootstrap(estimativa: float, replicas: np.ndarray, z: float = Z95, piso: float = 0.0) -> tuple[float, float]:
    """Intervalo normal em torno da estimativa, com o desvio-padrão das réplicas (como no iNEXT)."""
    dp = float(np.std(replicas, ddof=1)) if len(replicas) > 1 else 0.0
    return max(estimativa - z * dp, piso), estimativa + z * dp
