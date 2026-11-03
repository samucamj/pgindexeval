"""Construcao dos indices e medicao do tempo de build e do tamanho.

Reproduz o protocolo da dissertacao: a construcao de cada indice e repetida
'repeticoes_build' vezes; a cada repeticao o indice e removido e recriado, e o
tempo e cronometrado. Apos a ultima repeticao o indice permanece criado (para
a fase de consulta) e seu tamanho e medido com pg_relation_size.

Quando a criacao do indice e recusada pelo servidor (caso do trigrama GiST
sobre textos longos), a excecao e propagada para que o orquestrador registre o
cenario como INVIAVEL, sem interromper os demais.
"""

from __future__ import annotations

from time import perf_counter

from .config import Indice
from .db import Database


def medir_build(db: Database, indice: Indice, repeticoes: int) -> tuple[list[float], int]:
    """Constroi o indice 'repeticoes' vezes. Devolve (tempos_s, tamanho_bytes).

    Pode levantar psycopg.Error se o indice for inviavel (ex.: C4).
    O indice fica criado ao final, para a fase de consulta.
    """
    tempos: list[float] = []
    tamanho = 0
    for _ in range(repeticoes):
        db.executar(f"DROP INDEX IF EXISTS {indice.nome}")
        inicio = perf_counter()
        db.executar(indice.ddl)          # pode falhar -> cenario inviavel
        tempos.append(perf_counter() - inicio)
        tamanho = db.tamanho_indice(indice.nome)
    return tempos, tamanho


def limpar(db: Database, nomes: list[str]) -> None:
    """Remove os indices criados por este experimento."""
    for nome in nomes:
        db.executar(f"DROP INDEX IF EXISTS {nome}")
