"""Sintese e recomendacao a partir dos resultados.

Sem baseline: as estrategias sao comparadas entre si. A sintese identifica a
consulta mais rapida entre os cenarios viaveis, compara os cenarios que
respondem a mesma busca (quando houver) pelo custo de construcao e de disco, e
registra os cenarios inviaveis. Nenhum valor e inventado: tudo deriva das
medicoes.
"""

from __future__ import annotations

from .db import pretty_bytes
from .modelo import ResultadoCenario


def recomendar(resultados: list[ResultadoCenario]) -> str:
    viaveis = [r for r in resultados if r.viavel and r.consulta_resumo()]
    inviaveis = [r for r in resultados if not r.viavel]
    linhas: list[str] = []

    if viaveis:
        mais_rapido = min(viaveis, key=lambda r: r.consulta_resumo().media)
        q = mais_rapido.consulta_resumo().media
        linhas.append(
            f"Menor tempo de consulta entre os cenarios viaveis: "
            f"**{mais_rapido.id} {mais_rapido.nome}** ({q:.2f} ms)."
        )

    # cenarios que respondem a mesma busca (ex.: C1 e C2, FTS)
    por_busca: dict[str, list[ResultadoCenario]] = {}
    for r in viaveis:
        por_busca.setdefault(r.busca, []).append(r)
    for busca, grupo in por_busca.items():
        if len(grupo) < 2:
            continue
        grupo_ord = sorted(grupo, key=lambda r: r.build_resumo().media)
        barato = grupo_ord[0]
        caro = grupo_ord[-1]
        linhas.append(
            f"Para a busca '{busca}', comparando as estrategias de mesmo alvo: "
            f"{barato.id} {barato.nome} foi a mais economica na construcao "
            f"({barato.build_resumo().media:.1f} s, "
            f"{pretty_bytes(barato.tamanho_total())}), contra "
            f"{caro.build_resumo().media:.1f} s e "
            f"{pretty_bytes(caro.tamanho_total())} de {caro.id} {caro.nome}; "
            f"os tempos de consulta foram "
            f"{barato.consulta_resumo().media:.2f} ms e "
            f"{caro.consulta_resumo().media:.2f} ms, respectivamente."
        )

    for r in inviaveis:
        linhas.append(
            f"Cenario {r.id} {r.nome}: **inviavel**. {r.erro or ''}".strip()
        )

    linhas.append(
        "Nenhuma estrutura e universalmente superior: a escolha deve ponderar, "
        "em conjunto, o tempo de consulta, o custo de construcao e o espaco em disco."
    )
    return "\n\n".join(linhas)
