-- =====================================================================
--  inspecionar_schema.sql  -  levanta o schema do banco para montar o
--  workload e os cenarios reais da dissertacao. Somente leitura.
--  Uso (via psql_bd.bat, no banco original bd_mestrado):
--      C:\stjv\bats\psql_bd.bat C:\stjv\ptt\pgindexeval\sql\inspecionar_schema.sql
-- =====================================================================

\echo === 1) Tabelas de usuario: linhas aproximadas e tamanho ===
SELECT schemaname,
       relname                                   AS tabela,
       n_live_tup                                AS linhas_aprox,
       pg_size_pretty(pg_total_relation_size(relid)) AS tamanho_total
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

\echo
\echo === 2) Colunas das tabelas do schema public ===
SELECT table_name,
       ordinal_position AS pos,
       column_name,
       data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

\echo
\echo === 3) Indices ja existentes no schema public ===
SELECT tablename  AS tabela,
       indexname  AS indice,
       indexdef   AS definicao
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
