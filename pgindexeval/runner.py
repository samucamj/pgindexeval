"""Medicao do tempo de consulta de um cenario.

Reproduz o protocolo da dissertacao: a sessao e reiniciada (RESET ALL), a
varredura sequencial e desabilitada (SET enable_seqscan = off) para forcar o
uso do indice pretendido, aplicam-se as preparacoes do cenario (ex.:
SET ivfflat.probes = 10), executa-se um aquecimento do cache e, em seguida, a
consulta e medida 'repeticoes_consulta' vezes com EXPLAIN (ANALYZE, BUFFERS).
O plano de execucao e capturado para validar qual metodo de acesso foi usado.
"""

from __future__ import annotations

from .config import Cenario, Config
from .db import Database, extrair_plano


def preparar_sessao(db: Database, cfg: Config, cenario: Cenario) -> None:
    db.executar("RESET ALL")
    if not cfg.enable_seqscan:
        db.executar("SET enable_seqscan = off")
    for comando in cenario.preparacao:
        db.executar(comando)


def medir_consulta(db: Database, cfg: Config, cenario: Cenario) -> tuple[list[float], str]:
    """Devolve (tempos_ms, plano) para a consulta do cenario."""
    preparar_sessao(db, cfg, cenario)

    # aquecimento do cache (descartado)
    for _ in range(cfg.descartar_aquecimento):
        db.medir(cenario.consulta)

    tempos: list[float] = []
    plano = "?"
    for i in range(cfg.repeticoes_consulta):
        ms, raiz = db.medir(cenario.consulta)
        tempos.append(ms)
        if i == 0:
            plano = extrair_plano(raiz)

    db.executar("RESET ALL")
    return tempos, plano
