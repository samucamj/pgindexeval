"""Camada de acesso ao PostgreSQL (driver psycopg 3).

Abre a conexao, executa DDL (criar/remover indices) e SETs de sessao, mede o
tamanho de um indice (pg_relation_size) e mede o tempo de uma consulta com
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON), do qual extrai o "Execution Time"
(medido pelo servidor) e o plano de execucao.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg

# prioridade de nós de plano, para rotular o cenario como a dissertacao faz
_PRIORIDADE_PLANO = [
    "Bitmap Index Scan",
    "Index Scan",
    "Index Only Scan",
    "Bitmap Heap Scan",
    "Seq Scan",
]


def extrair_plano(no: dict[str, Any]) -> str:
    """Percorre a arvore do plano e devolve o no de acesso mais relevante."""
    tipos: list[str] = []

    def _walk(n: dict[str, Any]) -> None:
        tipos.append(n.get("Node Type", ""))
        for filho in n.get("Plans", []):
            _walk(filho)

    _walk(no)
    for alvo in _PRIORIDADE_PLANO:
        if alvo in tipos:
            return alvo
    return tipos[0] if tipos else "?"


class Database:
    def __init__(self, conexao: dict[str, Any]):
        self._params = conexao
        self.conn: psycopg.Connection | None = None

    def conectar(self) -> None:
        # autocommit: DDL e SET aplicam-se imediatamente a sessao.
        self.conn = psycopg.connect(**self._params, autocommit=True)

    def fechar(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "Database":
        self.conectar()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.fechar()

    def versao(self) -> str:
        assert self.conn is not None
        with self.conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            return row[0] if row else "desconhecida"

    def executar(self, sql: str) -> None:
        """Executa uma instrucao sem retorno (DDL, SET, RESET)."""
        assert self.conn is not None
        with self.conn.cursor() as cur:
            cur.execute(sql)

    def tamanho_indice(self, nome: str) -> int:
        """Tamanho do indice em bytes (0 se nao existir)."""
        assert self.conn is not None
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(pg_relation_size(to_regclass(%s)), 0)", (nome,)
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def medir(self, sql: str) -> tuple[float, dict[str, Any]]:
        """Mede uma consulta: devolve (tempo_ms, plano_raiz).

        Usa EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON); o tempo e o Execution Time
        informado pelo servidor.
        """
        assert self.conn is not None
        comando = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"
        with self.conn.cursor() as cur:
            cur.execute(comando)
            row = cur.fetchone()
        if not row:
            raise RuntimeError("EXPLAIN nao retornou resultado.")
        dados = row[0]
        if isinstance(dados, str):
            dados = json.loads(dados)
        obj = dados[0]
        return float(obj["Execution Time"]), obj["Plan"]


def pretty_bytes(n: int) -> str:
    """Formata bytes de modo semelhante a pg_size_pretty."""
    valor = float(n)
    for unidade in ("bytes", "kB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            if unidade == "bytes":
                return f"{int(valor)} bytes"
            return f"{valor:.1f} {unidade}"
        valor /= 1024.0
    return f"{n} bytes"
