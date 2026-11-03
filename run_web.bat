@echo off
REM =====================================================================
REM  run_web.bat  -  abre o aplicativo web do pgIndexEval no navegador.
REM  Uso: run_web.bat   (abre http://127.0.0.1:8765)
REM =====================================================================
setlocal
chcp 1252 >nul

set "PY=python"
where %PY% >nul 2>&1 || set "PY=py"

cd /d "%~dp0"
%PY% -m pgindexeval.webapp %*

endlocal
