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
    KeepTogether,
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
_CODE_BG = colors.HexColor("#1e2733")
_CODE_FG = colors.HexColor("#e6edf3")


def _fmt(v: Any, suf: str = "") -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") + suf
    return f"{v}{suf}"


def _xml(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _br(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


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
    secao = ParagraphStyle("secao", parent=ss["Normal"], fontSize=12,
                           textColor=_AZUL, spaceBefore=14, spaceAfter=4)
    estrtit = ParagraphStyle("estrtit", parent=ss["Normal"], fontSize=11,
                             textColor=_AZUL, spaceBefore=10, spaceAfter=2)
    ettit = ParagraphStyle("ettit", parent=ss["Normal"], fontSize=9.5,
                           spaceBefore=6, spaceAfter=1, leading=12)
    etdesc = ParagraphStyle("etdesc", parent=ss["Normal"], fontSize=8.5,
                            textColor=_CINZA, spaceAfter=3, leading=11)
    code = ParagraphStyle("code", parent=ss["Normal"], fontName="Courier",
                          fontSize=8, leading=11, textColor=_CODE_FG,
                          backColor=_CODE_BG, borderPadding=6, spaceAfter=4)
    stat = ParagraphStyle("stat", parent=ss["Normal"], fontSize=9,
                          textColor=_VERDE, backColor=_VERDE_BG, borderPadding=5,
                          spaceAfter=4, leading=12)

    def _code(txt: str) -> Paragraph:
        return Paragraph(_xml(txt).replace("\n", "<br/>"), code)

    def _reps(cab: str, vals: list, suf: str) -> Table:
        linhas = [[cab, "Tempo"]]
        for i, v in enumerate(vals, start=1):
            linhas.append([f"#{i}", _fmt(float(v), suf)])
        t = Table(linhas, colWidths=[24 * mm, 30 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _CAB_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _AZUL),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, _BORDA),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        return t

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
        _suf = (" (recomendado)" if c.get("recomendado")
                else " (semantica)" if c.get("semantica") else "")
        dados.append([
            Paragraph(c["nome"] + _suf, celula),
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

    # ----------------- Passo a passo das medicoes ----------------- #
    el.append(Paragraph("Passo a passo das medicoes", secao))
    el.append(Paragraph(
        "Para cada estrategia: construcao do indice (cada repeticao), leitura do "
        "catalogo (disco), medicao da consulta (com descarte de aquecimento) e "
        "limpeza. Sobre as repeticoes aplicam-se a media e o desvio-padrao amostral "
        "(divisao por n&minus;1). As estrategias sao comparadas entre si, sem cenario "
        "sem indice.", nota))

    for c in j.get("cenarios", []):
        p = c.get("passos", {}) or {}
        cr = p.get("criar", {}) or {}
        bloco: list[Any] = []
        titulo = c["nome"] + (" (recomendado)" if c.get("recomendado")
                              else " (semantica)" if c.get("semantica") else "")
        if c.get("situacao") != "viavel":
            bloco.append(Paragraph(f"{titulo} &mdash; inviavel", estrtit))
            if cr.get("ddl"):
                bloco.append(Paragraph("1. Tentativa de construcao", ettit))
                bloco.append(_code(cr["ddl"] + ";"))
            bloco.append(Paragraph(
                "<b>Inviavel:</b> " + _xml(cr.get("erro") or c.get("erro") or
                "o PostgreSQL recusou a criacao deste indice."), etdesc))
            el.append(KeepTogether(bloco))
            continue

        bloco.append(Paragraph(titulo, estrtit))
        # 1. construcao
        bloco.append(Paragraph(
            f"1. Construcao do indice &mdash; {cr.get('n', 1)}x (drop + create)", ettit))
        bloco.append(Paragraph(
            "O indice e removido e recriado; cada criacao e cronometrada.", etdesc))
        bloco.append(_code((cr.get("ddl") or "") + ";"))
        bloco.append(_reps("Repeticao", cr.get("repeticoes_s", []), " s"))
        bloco.append(Paragraph(
            f"Media = <b>{_fmt(cr.get('media_s'),' s')}</b> &middot; desvio amostral "
            f"(n&minus;1) = <b>{_fmt(cr.get('desvio_s'),' s')}</b>", stat))
        el.append(KeepTogether(bloco))

        # 2. disco
        cat = p.get("catalogo", {}) or {}
        b2: list[Any] = [Paragraph("2. Espaco em disco (catalogo do PostgreSQL)", ettit),
                         Paragraph("Tamanho lido direto do catalogo, sem estimativa.", etdesc),
                         _code(cat.get("sql", "")),
                         Paragraph(f"<b>{cat.get('legivel','—')}</b> "
                                   f"({_br(cat.get('bytes') or 0)} bytes)", etdesc)]
        el.append(KeepTogether(b2))

        # 3. consulta
        q = p.get("consulta", {}) or {}
        prep = ";\n".join(q.get("preparacao", []))
        if prep:
            prep += ";"
        b3: list[Any] = [
            Paragraph(f"3. Tempo de resposta da consulta &mdash; {q.get('n',0)}x "
                      "(medido pelo servidor)", ettit),
            Paragraph(f"Sessao reiniciada, varredura sequencial desabilitada; "
                      f"{q.get('aquecimento',0)} execucao(oes) de aquecimento "
                      "descartada(s); demais medidas pelo Execution Time do "
                      "EXPLAIN (ANALYZE).", etdesc),
            _code(prep + "\n\n" + (q.get("explain", "") or "") + ";"),
            _reps("Execucao", q.get("repeticoes_ms", []), " ms"),
            Paragraph(f"Media = <b>{_fmt(q.get('media_ms'),' ms')}</b> &middot; desvio "
                      f"amostral (n&minus;1) = <b>{_fmt(q.get('desvio_ms'),' ms')}</b> "
                      f"&middot; Plano: <b>{_xml(q.get('plano') or '—')}</b>", stat)]
        el.append(KeepTogether(b3))

        # 4. exclusao
        b4: list[Any] = [Paragraph("4. Exclusao e limpeza", ettit),
                         Paragraph("O indice de teste e removido; nada permanece na base.", etdesc),
                         _code((cr.get("drop_ddl") or "") + ";")]
        el.append(KeepTogether(b4))

    el.append(Spacer(1, 6))
    el.append(Paragraph(
        "Verde = indice recomendado (menor tempo de consulta). Os valores dependem "
        "do ambiente de medicao e constituem uma <b>sugestao</b> de apoio a decisao. "
        "pgIndexEval &middot; Produto Tecnico-Tecnologico &middot; MGTI/UCB.", nota))

    doc.build(el)
    return buf.getvalue()
