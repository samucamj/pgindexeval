"""Tratamento estatistico das medicoes.

Media e desvio-padrao amostral (ddof=1, divisao por n-1), conforme as Equacoes
1 e 2 da dissertacao. O denominador n-1 e apropriado porque as repeticoes sao
uma amostra das execucoes possiveis, e corrige a tendencia de subestimar a
dispersao real.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Resumo:
    n: int
    media: float
    desvio: float          # desvio-padrao amostral (n-1)

    @property
    def cv(self) -> float:
        return (self.desvio / self.media * 100.0) if self.media else 0.0


def resumir(valores: list[float]) -> Resumo:
    arr = np.asarray(valores, dtype=float)
    if arr.size == 0:
        return Resumo(n=0, media=0.0, desvio=0.0)
    media = float(arr.mean())
    desvio = float(arr.std(ddof=1)) if arr.size >= 2 else 0.0
    return Resumo(n=int(arr.size), media=media, desvio=desvio)
