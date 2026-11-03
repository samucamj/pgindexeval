@echo off
REM =====================================================================
REM  criar_atalho.bat  -  cria um atalho "pgIndexEval" na area de
REM  trabalho do Windows apontando para run_web.bat.
REM  Resolve a area de trabalho real (inclusive quando redirecionada
REM  pelo OneDrive). Basta executar uma vez (duplo clique).
REM =====================================================================
setlocal
set "ALVO=%~dp0run_web.bat"
set "PASTA=%~dp0"
set "ICONE=%SystemRoot%\System32\shell32.dll, 13"

powershell -NoProfile -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$link=Join-Path $d 'pgIndexEval.lnk';" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($link);" ^
  "$s.TargetPath='%ALVO%';" ^
  "$s.WorkingDirectory='%PASTA%';" ^
  "$s.IconLocation='%ICONE%';" ^
  "$s.Description='pgIndexEval - Avaliador de Indexacao (MGTI/UCB)';" ^
  "$s.Save();" ^
  "if(Test-Path $link){Write-Host ('Atalho criado na area de trabalho: '+$link)}else{Write-Host 'Nao foi possivel criar o atalho.'}"

endlocal
