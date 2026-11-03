"""Ponto de entrada da linha de comando do pgIndexEval.

Uso:
    python -m pgindexeval --config config_bd_mestrado.json
    python -m pgindexeval --config config_bd_mestrado.json --dry-run
    python -m pgindexeval --config config_bd_mestrado.json --saida resultados

Para cada cenario: constroi o(s) indice(s) medindo tempo e tamanho (3 repeticoes),
mede o tempo de consulta (10 repeticoes, com o cache aquecido e enable_seqscan=off),
captura o plano e, ao final, remove os indices que criou. Cenarios cujo indice
nao pode ser construido sao registrados como INVIAVEIS, sem interromper os demais.
Depois grava os artefatos de comprovacao e imprime a sintese.
"""

from __future__ import annotations

import argparse
import sys

import psycopg

from . import __version__
from .config import ErroConfig, carregar
from .db import Database, pretty_bytes
from .modelo import INVIAVEL, ResultadoCenario, ResultadoIndice
from .recommender import recomendar
from .report import gerar_todos
from .runner import medir_consulta
from .scenarios import limpar, medir_build


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pgindexeval",
        description="Avaliador de estrategias de indexacao em PostgreSQL "
                    "(3 metricas: build, disco, consulta).",
    )
    p.add_argument("--config", required=True, help="Caminho do JSON de configuracao.")
    p.add_argument("--saida", help="Diretorio de saida (sobrepoe o da configuracao).")
    p.add_argument("--dry-run", action="store_true",
                   help="Valida a configuracao e mostra o plano, sem conectar.")
    p.add_argument("--version", action="version", version=f"pgIndexEval {__version__}")
    return p.parse_args(argv)


def _plano(cfg) -> None:
    print(f"Configuracao valida. {len(cfg.cenarios)} cenarios. "
          f"build x{cfg.repeticoes_build}, consulta x{cfg.repeticoes_consulta}, "
          f"enable_seqscan={'on' if cfg.enable_seqscan else 'off'}.")
    for c in cfg.cenarios:
        idx = ", ".join(i.nome for i in c.indices)
        print(f"  - {c.id} {c.nome} | busca: {c.busca} | indice(s): {idx}")


def executar_cenario(db: Database, cfg, cen) -> ResultadoCenario:
    res = ResultadoCenario(id=cen.id, nome=cen.nome, busca=cen.busca)
    nomes = [i.nome for i in cen.indices]
    try:
        for indice in cen.indices:
            tempos, tamanho = medir_build(db, indice, cfg.repeticoes_build)
            res.indices.append(
                ResultadoIndice(nome=indice.nome, tempos=tempos, tamanho_bytes=tamanho)
            )
    except psycopg.Error as exc:
        res.situacao = INVIAVEL
        res.erro = str(exc).strip().splitlines()[0]
        limpar(db, nomes)
        print(f"          INVIAVEL: {res.erro}")
        return res

    b = res.build_resumo()
    print(f"          build medio: {b.media:.1f} s | disco: "
          f"{pretty_bytes(res.tamanho_total())}")
    res.consulta_tempos, res.plano = medir_consulta(db, cfg, cen)
    limpar(db, nomes)
    q = res.consulta_resumo()
    print(f"          consulta media: {q.media:.3f} ms | plano: {res.plano}")
    return res


def executar(cfg) -> tuple[list[ResultadoCenario], str]:
    resultados: list[ResultadoCenario] = []
    # Uniao de todos os indices gerenciados pelos cenarios. Removidos antes de
    # cada cenario para isolar o efeito: durante a medicao de um cenario, apenas
    # o seu proprio indice existe (a copia do banco ja trazia varios indices).
    todos = [i.nome for cen in cfg.cenarios for i in cen.indices]
    with Database(cfg.conexao) as db:
        versao = db.versao()
        print(f"Conectado: {versao}")
        for cen in cfg.cenarios:
            print(f"[cenario] {cen.id} - {cen.nome}")
            limpar(db, todos)
            resultados.append(executar_cenario(db, cfg, cen))
        limpar(db, todos)  # limpeza final
    return resultados, versao


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        cfg = carregar(args.config)
    except ErroConfig as exc:
        print(f"ERRO de configuracao: {exc}", file=sys.stderr)
        return 2
    if args.saida:
        cfg.saida = args.saida
    if args.dry_run:
        _plano(cfg)
        return 0

    try:
        resultados, versao = executar(cfg)
    except Exception as exc:
        print(f"ERRO de execucao: {exc}", file=sys.stderr)
        return 1

    recomendacao = recomendar(resultados)
    artefatos = gerar_todos(resultados, recomendacao, versao, cfg)

    print("\n=== Sintese ===")
    print(recomendacao)
    print("\n=== Artefatos gerados ===")
    for chave, caminho in artefatos.items():
        print(f"  {chave}: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
