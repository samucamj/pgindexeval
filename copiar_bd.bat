@echo off
REM =====================================================================
REM  copiar_bd.bat  -  cria a copia de testes bd_mestrado_ptt
REM                    a partir do banco original bd_mestrado.
REM
REM  IMPORTANTE: o PostgreSQL exige que NAO haja nenhuma sessao aberta
REM  em bd_mestrado durante a copia. Feche qualquer psql_bd.bat antes.
REM  A conexao e feita no banco de manutencao "postgres", nao no original.
REM =====================================================================
setlocal
chcp 1252 >nul

REM ---- localiza o psql (maior versao instalada) ----
set "PG_BIN="
for /d %%D in ("C:\Program Files\PostgreSQL\*") do (
    if exist "%%D\bin\psql.exe" set "PG_BIN=%%D\bin"
)
if not defined PG_BIN (
    echo psql.exe nao encontrado em C:\Program Files\PostgreSQL\*
    exit /b 1
)

set "PGHOST=127.0.0.1"
set "PGPORT=5432"
set "PGUSER=postgres"
REM Defina a senha antes de usar, ex.:  set "PGPASSWORD=sua_senha"
REM set "PGPASSWORD="

echo Removendo copia anterior (se existir)...
"%PG_BIN%\psql.exe" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS bd_mestrado_ptt;"
if errorlevel 1 goto :erro

echo Criando bd_mestrado_ptt a partir de bd_mestrado...
"%PG_BIN%\psql.exe" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE bd_mestrado_ptt WITH TEMPLATE bd_mestrado OWNER postgres;"
if errorlevel 1 goto :erro

echo.
echo Copia criada com sucesso: bd_mestrado_ptt
goto :fim

:erro
echo.
echo FALHA ao copiar. Verifique se nao ha sessoes abertas em bd_mestrado.

:fim
endlocal
