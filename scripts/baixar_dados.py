"""Baixa as bases públicas (OBIS, ETOPO1, Natural Earth) e grava o extrato agregado em data/.

A coleta no OBIS faz uma requisição por vez e leva algumas horas na primeira vez (cerca de 500
células x 4 faixas de profundidade x 3 recortes no tempo). É retomável: o bruto fica em
data/brutos/ e uma célula já baixada não é consultada de novo. Para refazer do zero, apague
data/brutos/.
"""

from __future__ import annotations

import sys
import time

from oceano_lacunas import dados


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    inicio = time.time()
    coleta = dados.baixar()
    print(f"Coleta de {coleta['coletado_em']}: {coleta['linhas']} em {(time.time() - inicio) / 60:.0f} min")
    print(f"Conferência (sha256, 16 primeiros): {coleta['sha256_16']}")


if __name__ == "__main__":
    main()
