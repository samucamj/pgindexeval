"""Ponto de entrada do executavel do pgIndexEval (PyInstaller).

Sobe o servidor web local e abre o navegador. Usado apenas para gerar o .exe
distribuivel; em desenvolvimento, continue usando `python -m pgindexeval.webapp`.
"""

from pgindexeval.webapp import main

if __name__ == "__main__":
    raise SystemExit(main())
