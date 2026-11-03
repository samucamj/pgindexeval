"""Geracao dos artefatos de saida (documentos comprobatorios do PTT).

Produz, no diretorio de saida:
  - consolidado.csv       : build medio, disco, consulta media e plano por cenario;
  - resultados_brutos.csv : todas as medicoes individuais (reprodutibilidade);
  - grafico_consulta.svg  : tempo medio de consulta por cenario (escala log);
  - grafico_build.svg     : tempo medio de construcao por cenario (escala log);
  - grafico_consulta.png / grafico_build.png : apenas se matplotlib existir;
  - relatorio.md          : sintese textual com a recomendacao.

As tabelas reproduzem a estrutura das Tabelas 3, 4 e 5 da dissertacao, e os
cenarios inviaveis (ex.: trigrama GiST) aparecem rotulados como tal.
"""

from __future__ import annotations

import csv
import math
import os
from datetime import datetime

from .db import pretty_bytes
from .modelo import ResultadoCenario


def _garantir_dir(caminho: str) -> None:
    os.makedirs(caminho, exist_ok=True)


def _xml(txt: str) -> str:
    return txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gravar_consolidado(resultados: list[ResultadoCenario], saida: str) -> str:
    destino = os.path.join(saida, "consolidado.csv")
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["cenario", "nome", "busca", "situacao",
             "build_medio_s", "build_desvio_s", "disco",
             "consulta_media_ms", "consulta_desvio_ms", "plano"]
        )
        for r in resultados:
            if not r.viavel:
                w.writerow([r.id, r.nome, r.busca, "inviavel",
                            "", "", "", "", "", r.erro or ""])
                continue
            b = r.build_resumo()
            q = r.consulta_resumo()
            w.writerow([
                r.id, r.nome, r.busca, "viavel",
                f"{b.media:.2f}" if b else "", f"{b.desvio:.2f}" if b else "",
                pretty_bytes(r.tamanho_total()),
                f"{q.media:.3f}" if q else "", f"{q.desvio:.3f}" if q else "",
                r.plano or "",
            ])
    return destino


def gravar_brutos(resultados: list[ResultadoCenario], saida: str) -> str:
    destino = os.path.join(saida, "resultados_brutos.csv")
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cenario", "tipo", "indice", "repeticao", "valor", "unidade"])
        for r in resultados:
            for idx in r.indices:
                for i, t in enumerate(idx.tempos, start=1):
                    w.writerow([r.id, "build", idx.nome, i, f"{t:.4f}", "s"])
            for i, t in enumerate(r.consulta_tempos, start=1):
                w.writerow([r.id, "consulta", "", i, f"{t:.4f}", "ms"])
    return destino


def _barras_svg(titulo: str, itens: list[tuple[str, float, str]], destino: str,
                unidade: str, log: bool = True) -> str:
    """itens: (rotulo, valor, anotacao). Barras horizontais, escala log opcional."""
    larg, alt_barra, pad, topo, esq = 760, 34, 28, 60, 230
    area = larg - esq - 130
    validos = [v for _, v, _ in itens if v > 0]
    if not validos:
        validos = [1.0]
    vmax = max(validos)
    vmin = min(validos)
    lo = math.log10(vmin) if log and vmin > 0 else 0.0
    hi = math.log10(vmax) if log and vmax > 0 else 0.0
    span = (hi - lo) or 1.0
    alt = topo + len(itens) * (alt_barra + 12) + pad

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{larg}" height="{alt}" '
        f'font-family="Segoe UI, Arial, sans-serif">',
        f'<rect width="{larg}" height="{alt}" fill="#ffffff"/>',
        f'<text x="{esq}" y="32" font-size="17" font-weight="bold" fill="#1a1a1a">'
        f'{_xml(titulo)}</text>',
    ]
    y = topo
    for rotulo, valor, anot in itens:
        if valor <= 0:
            w = 2.0
        elif log:
            w = 20 + (math.log10(valor) - lo) / span * (area - 20)
        else:
            w = (valor / vmax) * area
        svg.append(
            f'<text x="{esq - 10}" y="{y + alt_barra * 0.68:.0f}" font-size="12" '
            f'text-anchor="end" fill="#333">{_xml(rotulo)}</text>'
        )
        cor = "#b0b0b0" if valor <= 0 else "#4e79a7"
        svg.append(
            f'<rect x="{esq}" y="{y}" width="{w:.1f}" height="{alt_barra}" '
            f'rx="4" fill="{cor}"/>'
        )
        svg.append(
            f'<text x="{esq + w + 8:.1f}" y="{y + alt_barra * 0.68:.0f}" '
            f'font-size="12" fill="#333">{_xml(anot)}</text>'
        )
        y += alt_barra + 12
    escala = " (escala log)" if log else ""
    svg.append(
        f'<text x="{esq}" y="{alt - 8}" font-size="11" fill="#777">'
        f'unidade: {unidade}{escala}</text>'
    )
    svg.append("</svg>")
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))
    return destino


def gravar_graficos(resultados: list[ResultadoCenario], saida: str) -> list[str]:
    arts: list[str] = []

    consulta_itens = []
    for r in resultados:
        if r.viavel and r.consulta_resumo():
            q = r.consulta_resumo()
            consulta_itens.append((f"{r.id} {r.nome}", q.media, f"{q.media:.2f} ms"))
        else:
            consulta_itens.append((f"{r.id} {r.nome}", 0.0, "inviavel"))
    arts.append(_barras_svg(
        "pgIndexEval - tempo medio de consulta por cenario",
        consulta_itens, os.path.join(saida, "grafico_consulta.svg"), "ms", log=True))

    build_itens = []
    for r in resultados:
        b = r.build_resumo() if r.viavel else None
        if b:
            build_itens.append((f"{r.id} {r.nome}", b.media, f"{b.media:.1f} s"))
        else:
            build_itens.append((f"{r.id} {r.nome}", 0.0, "inviavel"))
    arts.append(_barras_svg(
        "pgIndexEval - tempo medio de construcao por cenario",
        build_itens, os.path.join(saida, "grafico_build.svg"), "s", log=True))

    arts += _graficos_png(resultados, saida)
    return arts


def _graficos_png(resultados: list[ResultadoCenario], saida: str) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    arts = []
    viaveis = [r for r in resultados if r.viavel and r.consulta_resumo()]
    if viaveis:
        nomes = [f"{r.id} {r.nome}" for r in viaveis]
        q = [r.consulta_resumo().media for r in viaveis]
        b = [r.build_resumo().media for r in viaveis]
        for valores, titulo, unid, arq in (
            (q, "Tempo medio de consulta", "ms", "grafico_consulta.png"),
            (b, "Tempo medio de construcao", "s", "grafico_build.png"),
        ):
            fig, ax = plt.subplots(figsize=(8, 0.6 * len(viaveis) + 1.5))
            ax.barh(nomes, valores, color="#4e79a7")
            ax.invert_yaxis()
            ax.set_xscale("log")
            ax.set_xlabel(unid)
            ax.set_title(titulo)
            fig.tight_layout()
            destino = os.path.join(saida, arq)
            fig.savefig(destino, dpi=150)
            plt.close(fig)
            arts.append(destino)
    return arts


def gravar_relatorio_md(resultados: list[ResultadoCenario], recomendacao: str,
                        versao_pg: str, cfg, saida: str) -> str:
    destino = os.path.join(saida, "relatorio.md")
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write("# Relatorio de avaliacao de indexacao - pgIndexEval\n\n")
        fh.write(f"- Data: {datetime.now():%Y-%m-%d %H:%M}\n")
        fh.write(f"- Servidor: {versao_pg}\n")
        fh.write(f"- Construcao repetida {cfg.repeticoes_build}x; "
                 f"consulta {cfg.repeticoes_consulta}x "
                 f"(descartadas {cfg.descartar_aquecimento} de aquecimento)\n")
        fh.write(f"- enable_seqscan: {'on' if cfg.enable_seqscan else 'off'}\n\n")
        fh.write("## Comparacao consolidada\n\n")
        fh.write("| Cenario | Busca | Build medio | Disco | Consulta media | Plano |\n")
        fh.write("|---|---|---:|---:|---:|---|\n")
        for r in resultados:
            if not r.viavel:
                fh.write(f"| {r.id} {r.nome} | {r.busca} | inviavel | — | — | — |\n")
                continue
            b = r.build_resumo()
            q = r.consulta_resumo()
            fh.write(
                f"| {r.id} {r.nome} | {r.busca} | "
                f"{b.media:.1f} s | {pretty_bytes(r.tamanho_total())} | "
                f"{q.media:.2f} ms | {r.plano} |\n"
            )
        fh.write("\n## Recomendacao\n\n")
        fh.write(recomendacao + "\n")
        fh.write("\n![Consulta](grafico_consulta.svg)\n\n")
        fh.write("![Construcao](grafico_build.svg)\n")
    return destino


def gerar_todos(resultados: list[ResultadoCenario], recomendacao: str,
                versao_pg: str, cfg) -> dict[str, str]:
    saida = cfg.saida
    _garantir_dir(saida)
    arts = {
        "consolidado": gravar_consolidado(resultados, saida),
        "brutos": gravar_brutos(resultados, saida),
        "relatorio": gravar_relatorio_md(resultados, recomendacao, versao_pg, cfg, saida),
    }
    for i, caminho in enumerate(gravar_graficos(resultados, saida)):
        arts[f"grafico_{i+1}"] = caminho
    return arts
