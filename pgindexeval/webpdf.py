"""Geracao do relatorio em PDF (reportlab).

Recebe o resultado ja calculado (o mesmo dicionario que a interface exibe) e
monta um PDF com cabecalho, metadados, a sugestao em destaque, a tabela das
tres metricas por cenario (com o indice recomendado realcado em verde) e o
aviso de que se trata de uma sugestao de apoio a decisao.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_AZUL = colors.HexColor("#2a4b7c")
_VERDE = colors.HexColor("#1b7f3b")
_VERDE_BG = colors.HexColor("#e6f4ea")
_CINZA = colors.HexColor("#5b6472")
_BORDA = colors.HexColor("#d8dde5")
_CAB_BG = colors.HexColor("#eef2f7")


def _fmt(v: Any, suf: str = "") -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") + suf
    return f"{v}{suf}"


def gerar_pdf(j: dict[str, Any]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Relatorio pgIndexEval",
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=16, textColor=_AZUL,
                        spaceAfter=4)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=_CINZA,
                         spaceAfter=10)
    corpo = ParagraphStyle("corpo", parent=ss["Normal"], fontSize=10, leading=14)
    sugest = ParagraphStyle("sugest", parent=corpo, backColor=_VERDE_BG,
                            borderColor=_VERDE, borderWidth=1, borderPadding=8,
                            leading=15, spaceAfter=12)
    nota = ParagraphStyle("nota", parent=ss["Normal"], fontSize=8,
                          textColor=_CINZA, spaceBefore=10)
    celula = ParagraphStyle("cel", parent=ss["Normal"], fontSize=9, leading=12)

    el: list[Any] = []
    tipo = "Simulacao de carga" if j.get("simulacao") else "Avaliacao de indexacao"
    el.append(Paragraph(f"pgIndexEval &mdash; {tipo}", h1))

    linhas = j.get("linhas")
    alvo = f"{j.get('tabela','')}.{j.get('coluna','')}"
    extra = f" &middot; multiplicador x{j.get('multiplicador')}" if j.get("simulacao") else ""
    el.append(Paragraph(
        f"Banco: {j.get('banco','—')} &middot; Alvo: {alvo} &middot; "
        f"Linhas: {linhas:,} {extra}<br/>".replace(",", ".") +
        f"Servidor: {j.get('versao','')}<br/>"
        f"Termo de busca: \"{j.get('termo','')}\" &middot; "
        f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", sub))

    rec = next((c for c in j.get("cenarios", []) if c.get("recomendado")), None)
    if rec:
        el.append(Paragraph(
            f"<b>Sugestao:</b> implementar <b>{rec['nome']}</b> &mdash; menor tempo "
            f"de consulta ({_fmt(rec['consulta_media_ms'],' ms')}), construcao "
            f"{_fmt(rec['build_medio_s'],' s')}, disco {rec['disco']}. "
            f"A decisao final deve ponderar, em conjunto, o tempo de consulta, o "
            f"custo de construcao e o espaco em disco.", sugest))

    cab = ["Estrategia", "Busca", "Construcao", "Disco", "Consulta", "Plano"]
    dados = [cab]
    idx_recomendado = None
    for i, c in enumerate(j.get("cenarios", []), start=1):
        if c.get("situacao") != "viavel":
            dados.append([Paragraph(c["nome"], celula),
                          Paragraph(c.get("busca", ""), celula),
                          Paragraph("<i>inviavel</i>", celula),
                          Paragraph(c.get("erro", "") or "—", celula), "—", "—"])
            continue
        if c.get("recomendado"):
            idx_recomendado = i
        dados.append([
            Paragraph(c["nome"] + (" (recomendado)" if c.get("recomendado") else ""), celula),
            Paragraph(c.get("busca", ""), celula),
            _fmt(c.get("build_medio_s"), " s"),
            c.get("disco") or "—",
            _fmt(c.get("consulta_media_ms"), " ms"),
            Paragraph(c.get("plano", "") or "—", celula),
        ])

    tabela = Table(dados, colWidths=[38*mm, 30*mm, 24*mm, 20*mm, 24*mm, 30*mm])
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _CAB_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _AZUL),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if idx_recomendado is not None:
        estilo.append(("BACKGROUND", (0, idx_recomendado), (-1, idx_recomendado), _VERDE_BG))
    tabela.setStyle(TableStyle(estilo))
    el.append(tabela)

    el.append(Paragraph(
        "Verde = indice recomendado (menor tempo de consulta). Os valores dependem "
        "do ambiente de medicao e constituem uma <b>sugestao</b> de apoio a decisao. "
        "pgIndexEval &middot; Produto Tecnico-Tecnologico &middot; MGTI/UCB.", nota))

    doc.build(el)
    return buf.getvalue()
