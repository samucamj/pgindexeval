@echo off
REM =====================================================================
REM  run_ptt.bat  -  executa o pgIndexEval no banco de testes (copia)
REM  Uso:
REM     run_ptt.bat                -> roda o experimento completo
REM     run_ptt.bat --dry-run      -> valida a configuracao, sem tocar no banco
REM  Le os parametros de conexao abaixo e usa config_bd_mestrado.json.
REM =====================================================================
setlocal
chcp 1252 >nul

REM ---- parametros de conexao (mesmos do psql_bd.bat) ----
set "PGHOST=127.0.0.1"
set "PGPORT=5432"
set "PGUSER=postgres"
REM Defina a senha antes de usar, ex.:  set "PGPASSWORD=sua_senha"
REM set "PGPASSWORD="

REM ---- localiza o python ----
set "PY=python"
where %PY% >nul 2>&1 || set "PY=py"

cd /d "%~dp0"
%PY% -m pgindexeval --config config_bd_mestrado.json %*

endlocal
