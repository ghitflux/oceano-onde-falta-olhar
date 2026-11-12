"""Desigualdade do esforço de amostragem: curva de Lorenz e índice de Gini ponderados por área.

A pergunta é "que fração do oceano concentra que fração dos registros". Cada unidade tem uma área
de oceano e um número de registros; as unidades são ordenadas pela densidade (registros por área),
da menos para a mais amostrada.
"""

from __future__ import annotations

import numpy as np


def curva_de_lorenz(registros, area) -> tuple[np.ndarray, np.ndarray]:
    """(fração acumulada da área, fração acumulada dos registros), começando em (0, 0).

    Unidades ordenadas pela densidade crescente. Com esforço uniforme a curva é a diagonal.
    """
    registros, area = np.asarray(registros, dtype=float), np.asarray(area, dtype=float)
    if np.any(area <= 0) or np.any(registros < 0):
        raise ValueError("área deve ser positiva e registros não negativos")
    ordem = np.argsort(registros / area, kind="stable")
    x = np.concatenate([[0.0], np.cumsum(area[ordem]) / area.sum()])
    total = registros.sum()
    y = np.concatenate([[0.0], np.cumsum(registros[ordem]) / total]) if total > 0 else np.zeros(x.size)
    return x, y


def gini(registros, area) -> float:
    """Gini ponderado por área: 1 − 2 · (área sob a curva de Lorenz). 0 = uniforme; perto de 1 = tudo
    num canto."""
    x, y = curva_de_lorenz(registros, area)
    return float(1 - 2 * np.trapezoid(y, x))


def fracao_da_area_com_metade(registros, area, parte: float = 0.5) -> float:
    """Fração da área, a mais densamente amostrada, que reúne `parte` dos registros."""
    x, y = curva_de_lorenz(registros, area)
    return float(1 - np.interp(1 - parte, y, x))


def fracao_dos_registros_no_topo(registros, area, topo: float = 0.1) -> float:
    """Fração dos registros que está nos `topo` da área mais densamente amostrada."""
    x, y = curva_de_lorenz(registros, area)
    return float(1 - np.interp(1 - topo, x, y))
