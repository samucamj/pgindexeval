"""Carregamento e validacao do arquivo de configuracao (JSON).

Modelo alinhado ao protocolo experimental da dissertacao: cada cenario associa
uma busca a uma estrategia de indexacao e e avaliado em tres metricas (tempo de
construcao, tamanho em disco e tempo de consulta). Nao ha cenario "baseline"
sem indice; as estrategias sao comparadas entre si. Um cenario pode resultar
INVIAVEL quando o indice nao pode ser construido (caso do trigrama GiST).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


class ErroConfig(Exception):
    """Erro de validacao da configuracao."""


@dataclass
class Indice:
    nome: str          # nome do indice (usado para medir tamanho e remover)
    ddl: str           # instrucao CREATE INDEX


@dataclass
class Cenario:
    id: str
    nome: str
    busca: str                              # descricao da busca (ex.: "FTS: habeas & corpus")
    indices: list[Indice]
    consulta: str                           # SQL medido com EXPLAIN ANALYZE
    preparacao: list[str] = field(default_factory=list)  # SETs antes da consulta


@dataclass
class Config:
    conexao: dict[str, Any]
    cenarios: list[Cenario]
    repeticoes_consulta: int = 10
    repeticoes_build: int = 3
    descartar_aquecimento: int = 1
    enable_seqscan: bool = False            # False => "SET enable_seqscan = off"
    saida: str = "resultados"


def _resolver_conexao(bruto: dict[str, Any]) -> dict[str, Any]:
    conexao = dict(bruto)
    if not conexao.get("password"):
        env = os.environ.get("PGPASSWORD")
        if env:
            conexao["password"] = env
    conexao.pop("comentario", None)
    conexao.pop("comment", None)
    return conexao


def _ler_indices(cen: dict[str, Any], cid: str) -> list[Indice]:
    brutos = cen.get("indices", [])
    if not brutos:
        raise ErroConfig(f"Cenario '{cid}': informe ao menos um indice.")
    indices: list[Indice] = []
    for i in brutos:
        if "nome" not in i or "ddl" not in i:
            raise ErroConfig(
                f"Cenario '{cid}': cada indice precisa de 'nome' e 'ddl'."
            )
        indices.append(Indice(nome=i["nome"], ddl=i["ddl"]))
    return indices


def carregar(caminho: str) -> Config:
    """Le o JSON de configuracao e devolve um objeto Config validado."""
    if not os.path.isfile(caminho):
        raise ErroConfig(f"Arquivo de configuracao nao encontrado: {caminho}")

    with open(caminho, encoding="utf-8") as fh:
        try:
            bruto = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ErroConfig(f"JSON invalido em {caminho}: {exc}") from exc

    for chave in ("conexao", "cenarios"):
        if chave not in bruto:
            raise ErroConfig(f"Chave obrigatoria ausente: '{chave}'")

    cenarios: list[Cenario] = []
    for c in bruto["cenarios"]:
        cid = c.get("id")
        if not cid:
            raise ErroConfig("Ha cenario sem 'id'.")
        if "consulta" not in c or not c["consulta"].strip():
            raise ErroConfig(f"Cenario '{cid}': falta a 'consulta'.")
        cenarios.append(
            Cenario(
                id=cid,
                nome=c.get("nome", cid),
                busca=c.get("busca", ""),
                indices=_ler_indices(c, cid),
                consulta=c["consulta"],
                preparacao=c.get("preparacao", []),
            )
        )

    if len(cenarios) < 2:
        raise ErroConfig("Defina ao menos 2 cenarios para comparar.")
    ids = [c.id for c in cenarios]
    if len(ids) != len(set(ids)):
        raise ErroConfig("Ha cenarios com 'id' repetido.")

    cfg = Config(
        conexao=_resolver_conexao(bruto["conexao"]),
        cenarios=cenarios,
        repeticoes_consulta=int(bruto.get("repeticoes_consulta", 10)),
        repeticoes_build=int(bruto.get("repeticoes_build", 3)),
        descartar_aquecimento=int(bruto.get("descartar_aquecimento", 1)),
        enable_seqscan=bool(bruto.get("enable_seqscan", False)),
        saida=bruto.get("saida", "resultados"),
    )
    if cfg.repeticoes_consulta < 2:
        raise ErroConfig("repeticoes_consulta deve ser >= 2 (para o desvio n-1).")
    if cfg.repeticoes_build < 1:
        raise ErroConfig("repeticoes_build deve ser >= 1.")
    return cfg
