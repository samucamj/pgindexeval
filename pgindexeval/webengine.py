"""Motor do aplicativo web do pgIndexEval.

Generaliza o experimento da dissertacao para qualquer tabela e coluna textual
escolhidas pelo gestor: constroi os cenarios de indexacao de texto, executa o
ciclo criar -> medir -> relatorio -> remover e devolve resultados prontos para
a interface (JSON), destacando a estrategia recomendada.

Reutiliza os modulos do nucleo (config, db, scenarios, runner, modelo, stats).
Seguranca: identificadores (tabela/coluna) sao validados contra o catalogo e
citados entre aspas; o termo de busca e escapado como literal.
"""

from __future__ import annotations

from typing import Any

import psycopg

from . import config, db, scenarios
from .modelo import INVIAVEL, ResultadoCenario, ResultadoIndice
from .runner import medir_consulta
from .scenarios import medir_build

# Catalogo de estrategias de indexacao de texto oferecidas ao gestor.
# Cada uma sabe gerar sua DDL de indice e a consulta correspondente.
ESTRATEGIAS = {
    "fts_gin": {"nome": "FTS GIN", "busca": "Full-Text Search"},
    "fts_gist": {"nome": "FTS GiST", "busca": "Full-Text Search"},
    "trgm_gin": {"nome": "Trigrama GIN", "busca": "Similaridade (ILIKE)"},
    "trgm_gist": {"nome": "Trigrama GiST", "busca": "Similaridade (ILIKE)"},
    "ivfflat": {"nome": "Vetorial IVFFlat", "busca": "Semantica (vetor)"},
}

# Estrategias de texto (usam a coluna textual + termo); o IVFFlat e semantico
# (usa uma coluna vetorial) e forma familia propria, sem ranking cruzado.
ESTRATEGIAS_TEXTO = {"fts_gin", "fts_gist", "trgm_gin", "trgm_gist"}
ESTRATEGIAS_FTS = {"fts_gin", "fts_gist"}

# Memoria de manutencao da sessao de construcao dos indices. Reproduz o
# protocolo da dissertacao (SET maintenance_work_mem = '512MB'), que acelera o
# build; e um ajuste de sessao, aplicado apenas enquanto o experimento roda.
MANUTENCAO_MEM = "512MB"


# --------------------------------------------------------------------------- #
# Utilidades de seguranca
# --------------------------------------------------------------------------- #
def _ident(nome: str) -> str:
    """Cita um identificador SQL, dobrando aspas internas."""
    return '"' + nome.replace('"', '""') + '"'


def _literal(txt: str) -> str:
    """Escapa um literal de texto para uso direto em SQL."""
    return txt.replace("'", "''")


def _conexao(params: dict[str, Any], dbname: str | None = None) -> dict[str, Any]:
    c = {
        "host": params.get("host", "127.0.0.1"),
        "port": int(params.get("port", 5432)),
        "user": params.get("user", "postgres"),
        "password": params.get("password", ""),
    }
    alvo = dbname or params.get("dbname")
    if alvo:
        c["dbname"] = alvo
    return c


# --------------------------------------------------------------------------- #
# Inspecao do ambiente
# --------------------------------------------------------------------------- #
def inspecionar(params: dict[str, Any]) -> dict[str, Any]:
    """Versao do servidor e lista de bancos de dados."""
    with db.Database(_conexao(params, "postgres")) as database:
        versao = database.versao()
        assert database.conn is not None
        with database.conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = false ORDER BY datname"
            )
            bancos = [r[0] for r in cur.fetchall()]
    return {"versao": versao, "bancos": bancos}


def listar_tabelas(params: dict[str, Any]) -> dict[str, Any]:
    with db.Database(_conexao(params)) as database:
        assert database.conn is not None
        with database.conn.cursor() as cur:
            cur.execute(
                "SELECT relname, n_live_tup, "
                "pg_size_pretty(pg_total_relation_size(relid)) "
                "FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC"
            )
            tabelas = [
                {"tabela": r[0], "linhas": int(r[1]), "tamanho": r[2]}
                for r in cur.fetchall()
            ]
    return {"tabelas": tabelas}


def listar_colunas(params: dict[str, Any]) -> dict[str, Any]:
    tabela = params["tabela"]
    with db.Database(_conexao(params)) as database:
        assert database.conn is not None
        with database.conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type, udt_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position",
                (tabela,),
            )
            linhas = cur.fetchall()
    textuais = {"text", "character varying", "character", "citext"}
    colunas = [
        {"coluna": n, "tipo": t, "textual": t in textuais,
         "vetorial": (u == "vector"), "tsvector": (u == "tsvector")}
        for n, t, u in linhas
    ]
    if not colunas:
        raise ValueError(f"Tabela '{tabela}' nao encontrada no schema public.")
    return {"colunas": colunas}


def _validar(params: dict[str, Any]) -> tuple[str, str]:
    """Confere que tabela e coluna existem; devolve (tabela, coluna)."""
    tabela = params["tabela"]
    coluna = params["coluna"]
    cols = listar_colunas(params)["colunas"]
    nomes = {c["coluna"] for c in cols}
    if coluna not in nomes:
        raise ValueError(f"Coluna '{coluna}' nao existe em '{tabela}'.")
    return tabela, coluna


# --------------------------------------------------------------------------- #
# Construcao dos cenarios para a tabela/coluna escolhidas
# --------------------------------------------------------------------------- #
def construir_cenarios(
    tabela: str, coluna: str, termo: str, estrategias: list[str],
    coluna_vetor: str | None = None, coluna_tsv: str | None = None,
) -> list[config.Cenario]:
    t = _ident(tabela)
    c = _ident(coluna)
    termo_sql = _literal(termo)
    # FTS: se houver uma coluna tsvector materializada (coluna gerada STORED,
    # como na dissertacao), indexa-se essa coluna diretamente -- o build nao
    # recalcula to_tsvector e a comparacao GIN x GiST usa o MESMO tsvector.
    # Sem ela, recai no indice funcional (recalcula o tsvector a cada build).
    if coluna_tsv:
        expr_fts = _ident(coluna_tsv)
    else:
        expr_fts = f"to_tsvector('portuguese', coalesce({c}, ''))"
    consulta_fts = (
        f"SELECT ctid FROM {t} "
        f"WHERE {expr_fts} @@ plainto_tsquery('portuguese', '{termo_sql}') LIMIT 20"
    )
    consulta_ilike = (
        f"SELECT ctid FROM {t} WHERE {c} ILIKE '%{termo_sql}%' LIMIT 20"
    )
    defs = {
        "fts_gin": config.Cenario(
            id="fts_gin", nome="FTS GIN", busca="Full-Text Search",
            indices=[config.Indice("pie_eval_fts_gin",
                     f"CREATE INDEX pie_eval_fts_gin ON {t} USING gin ({expr_fts})")],
            consulta=consulta_fts),
        "fts_gist": config.Cenario(
            id="fts_gist", nome="FTS GiST", busca="Full-Text Search",
            indices=[config.Indice("pie_eval_fts_gist",
                     f"CREATE INDEX pie_eval_fts_gist ON {t} USING gist ({expr_fts})")],
            consulta=consulta_fts),
        "trgm_gin": config.Cenario(
            id="trgm_gin", nome="Trigrama GIN", busca="Similaridade (ILIKE)",
            indices=[config.Indice("pie_eval_trgm_gin",
                     f"CREATE INDEX pie_eval_trgm_gin ON {t} USING gin ({c} gin_trgm_ops)")],
            consulta=consulta_ilike),
        "trgm_gist": config.Cenario(
            id="trgm_gist", nome="Trigrama GiST", busca="Similaridade (ILIKE)",
            indices=[config.Indice("pie_eval_trgm_gist",
                     f"CREATE INDEX pie_eval_trgm_gist ON {t} USING gist ({c} gist_trgm_ops)")],
            consulta=consulta_ilike),
    }
    if coluna_vetor:
        v = _ident(coluna_vetor)
        # vetor de referencia tirado da propria tabela (como no cenario C5)
        consulta_vec = (
            f"SELECT ctid FROM {t} WHERE {v} IS NOT NULL "
            f"ORDER BY {v} <=> ("
            f"SELECT {v} FROM {t} WHERE {v} IS NOT NULL ORDER BY ctid LIMIT 1"
            f") LIMIT 20"
        )
        defs["ivfflat"] = config.Cenario(
            id="ivfflat", nome="Vetorial IVFFlat", busca="Semantica (vetor)",
            indices=[config.Indice(
                "pie_eval_ivfflat",
                f"CREATE INDEX pie_eval_ivfflat ON {t} "
                f"USING ivfflat ({v} vector_cosine_ops) WITH (lists = 100)")],
            consulta=consulta_vec,
            preparacao=["SET ivfflat.probes = 10"])
    return [defs[e] for e in estrategias if e in defs]


# --------------------------------------------------------------------------- #
# Execucao e serializacao
# --------------------------------------------------------------------------- #
def _rodar_cenario(database: db.Database, cfg: config.Config,
                   cen: config.Cenario) -> ResultadoCenario:
    res = ResultadoCenario(id=cen.id, nome=cen.nome, busca=cen.busca)
    nomes = [i.nome for i in cen.indices]
    try:
        for indice in cen.indices:
            tempos, tamanho = medir_build(database, indice, cfg.repeticoes_build)
            res.indices.append(ResultadoIndice(indice.nome, tempos, tamanho))
    except psycopg.Error as exc:
        res.situacao = INVIAVEL
        res.erro = str(exc).strip().splitlines()[0]
        scenarios.limpar(database, nomes)
        return res
    res.consulta_tempos, res.plano = medir_consulta(database, cfg, cen)
    scenarios.limpar(database, nomes)
    return res


def _passos(res: ResultadoCenario, cen: config.Cenario,
            cfg: config.Config) -> dict[str, Any]:
    """Monta o detalhamento didatico (passo a passo) de um cenario.

    Expoe, para a interface, os scripts executados e as medicoes individuais de
    cada repeticao, para que o gestor veja o processo, e nao apenas o resumo.
    """
    ind = cen.indices[0] if cen.indices else None
    criar: dict[str, Any] = {
        "nome_indice": ind.nome if ind else None,
        "ddl": (ind.ddl if ind else None),
        "drop_ddl": (f"DROP INDEX IF EXISTS {ind.nome}" if ind else None),
        "sessao": f"SET maintenance_work_mem = '{MANUTENCAO_MEM}'",
        "n": cfg.repeticoes_build,
    }
    if res.viavel and res.indices:
        b = res.build_resumo()
        criar["repeticoes_s"] = [round(t, 3) for t in res.indices[0].tempos]
        criar["media_s"] = round(b.media, 3) if b else None
        criar["desvio_s"] = round(b.desvio, 3) if b else None
    else:
        criar["erro"] = res.erro

    passos: dict[str, Any] = {"criar": criar}

    if res.viavel and res.indices:
        nome = res.indices[0].nome
        bytes_ = res.tamanho_total()
        passos["catalogo"] = {
            "sql": f"SELECT pg_relation_size('{nome}') AS bytes;",
            "sql_legivel": f"SELECT pg_size_pretty(pg_relation_size('{nome}'));",
            "bytes": bytes_,
            "legivel": db.pretty_bytes(bytes_),
        }
        prep = ["RESET ALL"]
        if not cfg.enable_seqscan:
            prep.append("SET enable_seqscan = off")
        prep += list(cen.preparacao)
        q = res.consulta_resumo()
        passos["consulta"] = {
            "preparacao": prep,
            "consulta_sql": cen.consulta,
            "explain": f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)\n{cen.consulta}",
            "aquecimento": cfg.descartar_aquecimento,
            "n": cfg.repeticoes_consulta,
            "repeticoes_ms": [round(t, 3) for t in res.consulta_tempos],
            "media_ms": round(q.media, 3) if q else None,
            "desvio_ms": round(q.desvio, 3) if q else None,
            "plano": res.plano,
        }
    return passos


def _serializar(res: ResultadoCenario, cen: config.Cenario,
                cfg: config.Config) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": res.id, "nome": res.nome, "busca": res.busca,
        "situacao": res.situacao, "erro": res.erro, "plano": res.plano,
        "recomendado": False, "semantica": res.id == "ivfflat",
    }
    b = res.build_resumo() if res.viavel else None
    q = res.consulta_resumo() if res.viavel else None
    d["build_medio_s"] = round(b.media, 2) if b else None
    d["build_desvio_s"] = round(b.desvio, 2) if b else None
    d["disco_bytes"] = res.tamanho_total() if res.viavel else None
    d["disco"] = db.pretty_bytes(res.tamanho_total()) if res.viavel else None
    d["consulta_media_ms"] = round(q.media, 3) if q else None
    d["consulta_desvio_ms"] = round(q.desvio, 3) if q else None
    d["passos"] = _passos(res, cen, cfg)
    return d


def _marcar_recomendado(cenarios: list[dict[str, Any]]) -> str | None:
    """Marca em verde o de menor tempo de consulta entre os viaveis.

    A busca vetorial (semantica) responde a outra pergunta e nao e comparada
    com as estrategias de texto: fica de fora do ranking. So e marcada se for a
    unica familia viavel escolhida.
    """
    viaveis = [c for c in cenarios if c["situacao"] == "viavel"
               and c["consulta_media_ms"] is not None]
    if not viaveis:
        return None
    texto = [c for c in viaveis if not c.get("semantica")]
    pool = texto or viaveis
    melhor = min(pool, key=lambda c: c["consulta_media_ms"])
    melhor["recomendado"] = True
    return melhor["id"]


def _contar_linhas(database: db.Database, tabela: str) -> int:
    assert database.conn is not None
    with database.conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {_ident(tabela)}")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _executar(conexao: dict[str, Any], cenarios: list[config.Cenario],
              reps_build: int, reps_consulta: int) -> tuple[list[dict], str, str | None]:
    cfg = config.Config(
        conexao=conexao, cenarios=cenarios,
        repeticoes_build=reps_build, repeticoes_consulta=reps_consulta,
        enable_seqscan=False,
    )
    resultados: list[ResultadoCenario] = []
    precisa_trgm = any(c.id.startswith("trgm") for c in cenarios)
    precisa_vector = any(c.id == "ivfflat" for c in cenarios)
    with db.Database(conexao) as database:
        versao = database.versao()
        # Ajuste de sessao que acelera a construcao (igual a dissertacao).
        database.executar(f"SET maintenance_work_mem = '{MANUTENCAO_MEM}'")
        if precisa_trgm:
            database.executar("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        if precisa_vector:
            database.executar("CREATE EXTENSION IF NOT EXISTS vector")
        todos = [i.nome for c in cenarios for i in c.indices]
        for cen in cenarios:
            scenarios.limpar(database, todos)
            resultados.append(_rodar_cenario(database, cfg, cen))
        scenarios.limpar(database, todos)
    dados = [_serializar(r, cen, cfg) for r, cen in zip(resultados, cenarios)]
    recomendado = _marcar_recomendado(dados)
    return dados, versao, recomendado


def avaliar(params: dict[str, Any]) -> dict[str, Any]:
    tabela, coluna = _validar(params)
    estrategias = params.get("estrategias") or ["fts_gin", "fts_gist"]
    termo = params.get("termo", "").strip()
    usa_texto = any(e in ESTRATEGIAS_TEXTO for e in estrategias)
    if usa_texto and not termo:
        raise ValueError("Informe um termo de busca de exemplo.")

    cols: list[dict[str, Any]] | None = None
    coluna_vetor = (params.get("coluna_vetor") or "").strip() or None
    if "ivfflat" in estrategias:
        if not coluna_vetor:
            raise ValueError(
                "Selecione a coluna vetorial (embedding) para a busca IVFFlat.")
        cols = listar_colunas(params)["colunas"]
        if coluna_vetor not in {c["coluna"] for c in cols if c["vetorial"]}:
            raise ValueError(
                f"A coluna '{coluna_vetor}' nao e do tipo vector em '{tabela}'.")

    # FTS fiel a dissertacao: usa uma coluna tsvector materializada, se houver.
    # Vem da interface (coluna_tsv) ou e autodetectada (primeira coluna tsvector).
    coluna_tsv = (params.get("coluna_tsv") or "").strip() or None
    if any(e in ESTRATEGIAS_FTS for e in estrategias):
        if cols is None:
            cols = listar_colunas(params)["colunas"]
        tsv_cols = [c["coluna"] for c in cols if c["tsvector"]]
        if coluna_tsv:
            if coluna_tsv not in tsv_cols:
                raise ValueError(
                    f"A coluna '{coluna_tsv}' nao e do tipo tsvector em '{tabela}'.")
        else:
            coluna_tsv = tsv_cols[0] if tsv_cols else None

    reps_build = max(1, int(params.get("repeticoes_build", 1)))
    reps_consulta = max(2, int(params.get("repeticoes_consulta", 5)))
    conexao = _conexao(params)

    with db.Database(conexao) as database:
        linhas = _contar_linhas(database, tabela)

    cenarios = construir_cenarios(
        tabela, coluna, termo, estrategias, coluna_vetor, coluna_tsv)
    dados, versao, recomendado = _executar(conexao, cenarios, reps_build, reps_consulta)
    return {
        "versao": versao, "banco": params.get("dbname"),
        "tabela": tabela, "coluna": coluna, "coluna_vetor": coluna_vetor,
        "coluna_tsv": coluna_tsv,
        "termo": termo, "linhas": linhas,
        "cenarios": dados, "recomendado": recomendado, "simulacao": False,
    }


# --------------------------------------------------------------------------- #
# Simulacao de carga (outra tela)
# --------------------------------------------------------------------------- #
def simular(params: dict[str, Any]) -> dict[str, Any]:
    """Projeta o comportamento com mais dados.

    Cria uma tabela temporaria com apenas a coluna textual, replicada por um
    multiplicador (crescimento) a partir de uma amostra-base, roda os cenarios
    sobre ela e devolve os resultados rotulados como simulacao. Ao final, a
    tabela temporaria e removida.
    """
    tabela, coluna = _validar(params)
    termo = params.get("termo", "").strip() or "exemplo"
    estrategias = [e for e in (params.get("estrategias") or ["fts_gin", "fts_gist"])
                   if e in ESTRATEGIAS_TEXTO]
    if not estrategias:
        raise ValueError(
            "A simulacao de carga projeta apenas a busca textual (replica a coluna "
            "de texto). Selecione ao menos uma estrategia de texto; a busca vetorial "
            "IVFFlat nao entra na simulacao.")
    multiplicador = max(1, min(int(params.get("multiplicador", 2)), 5))
    base = int(params.get("linhas_base", 0))  # 0 = todas as linhas
    reps_build = max(1, int(params.get("repeticoes_build", 1)))
    reps_consulta = max(2, int(params.get("repeticoes_consulta", 5)))
    conexao = _conexao(params)

    t = _ident(tabela)
    c = _ident(coluna)
    sim = "pie_sim"
    limite = f"LIMIT {base}" if base > 0 else ""
    cria_sim = (
        f"CREATE TABLE {sim} AS "
        f"SELECT s.txt FROM (SELECT coalesce({c}, '')::text AS txt FROM {t} {limite}) s "
        f"CROSS JOIN generate_series(1, {multiplicador})"
    )

    with db.Database(conexao) as database:
        database.executar(f"DROP TABLE IF EXISTS {sim}")
        try:
            database.executar(cria_sim)
            database.executar(f"ANALYZE {sim}")
            linhas_sim = _contar_linhas(database, sim)
        except psycopg.Error as exc:
            database.executar(f"DROP TABLE IF EXISTS {sim}")
            raise ValueError(f"Falha ao preparar a simulacao: {exc}") from exc

    cenarios = construir_cenarios(sim, "txt", termo, estrategias)
    try:
        dados, versao, recomendado = _executar(
            conexao, cenarios, reps_build, reps_consulta
        )
    finally:
        with db.Database(conexao) as database:
            database.executar(f"DROP TABLE IF EXISTS {sim}")

    return {
        "versao": versao, "banco": params.get("dbname"),
        "tabela": tabela, "coluna": coluna, "termo": termo,
        "linhas": linhas_sim, "multiplicador": multiplicador,
        "cenarios": dados, "recomendado": recomendado, "simulacao": True,
    }
