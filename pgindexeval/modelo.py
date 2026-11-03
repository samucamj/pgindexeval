"""Estruturas de resultado de cada cenario.

Reunem o que foi medido por cenario: o(s) indice(s) com tempos de construcao e
tamanho, os tempos de consulta e o plano observado, alem da situacao (viavel ou
inviavel). Os metodos agregam as medicoes em resumos estatisticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .stats import Resumo, resumir

VIAVEL = "viavel"
INVIAVEL = "inviavel"


@dataclass
class ResultadoIndice:
    nome: str
    tempos: list[float]        # tempos de construcao, em segundos
    tamanho_bytes: int


@dataclass
class ResultadoCenario:
    id: str
    nome: str
    busca: str
    situacao: str = VIAVEL
    erro: str | None = None
    indices: list[ResultadoIndice] = field(default_factory=list)
    consulta_tempos: list[float] = field(default_factory=list)  # ms
    plano: str | None = None

    @property
    def viavel(self) -> bool:
        return self.situacao == VIAVEL

    def build_resumo(self) -> Resumo | None:
        """Resumo do tempo total de construcao (soma dos indices por repeticao)."""
        if not self.indices:
            return None
        r = len(self.indices[0].tempos)
        if r == 0:
            return None
        totais = [sum(idx.tempos[i] for idx in self.indices) for i in range(r)]
        return resumir(totais)

    def tamanho_total(self) -> int:
        return sum(idx.tamanho_bytes for idx in self.indices)

    def consulta_resumo(self) -> Resumo | None:
        if not self.consulta_tempos:
            return None
        return resumir(self.consulta_tempos)
