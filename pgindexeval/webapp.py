"""Aplicativo web do pgIndexEval (servidor da biblioteca padrao).

Serve uma pagina unica e expoe endpoints JSON que acionam o motor
(webengine). Nao exige frameworks: usa http.server. Para o gestor, basta:

    python -m pgindexeval.webapp         (abre em http://127.0.0.1:8765)

Vincula-se somente a 127.0.0.1 (uso local). Os dados de conexao sao enviados
pela interface a cada acao e nao ficam gravados.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import webengine, webpdf

HOST = "127.0.0.1"
PORT = 8765


def _localizar_web() -> str:
    # Em executavel PyInstaller, os dados ficam em sys._MEIPASS/web.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "web")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


_WEB_DIR = _localizar_web()
_servidor: ThreadingHTTPServer | None = None  # definido em main(), p/ o encerramento

_ROTAS = {
    "/api/inspecionar": webengine.inspecionar,
    "/api/tabelas": webengine.listar_tabelas,
    "/api/colunas": webengine.listar_colunas,
    "/api/avaliar": webengine.avaliar,
    "/api/simular": webengine.simular,
}


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo: int, obj: dict) -> None:
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        caminho = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
        arquivo = os.path.normpath(os.path.join(_WEB_DIR, caminho))
        if not arquivo.startswith(_WEB_DIR) or not os.path.isfile(arquivo):
            self._enviar(404, b"nao encontrado", "text/plain; charset=utf-8")
            return
        tipo = "text/html; charset=utf-8" if arquivo.endswith(".html") else \
               "text/css" if arquivo.endswith(".css") else \
               "application/javascript" if arquivo.endswith(".js") else \
               "application/octet-stream"
        with open(arquivo, "rb") as fh:
            self._enviar(200, fh.read(), tipo)

    def _ler_corpo(self) -> dict:
        tam = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(tam) or b"{}")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/pdf":
            self._gerar_pdf()
            return
        if self.path == "/api/encerrar":
            self._json(200, {"ok": True})
            if _servidor is not None:
                threading.Thread(target=_servidor.shutdown, daemon=True).start()
            return
        funcao = _ROTAS.get(self.path)
        if funcao is None:
            self._json(404, {"erro": "rota desconhecida"})
            return
        try:
            self._json(200, funcao(self._ler_corpo()))
        except Exception as exc:  # devolve o erro de forma legivel a interface
            self._json(200, {"erro": str(exc)})

    def _gerar_pdf(self) -> None:
        try:
            pdf = webpdf.gerar_pdf(self._ler_corpo())
        except Exception as exc:
            self._json(200, {"erro": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition",
                         'attachment; filename="relatorio_pgindexeval.pdf"')
        self.send_header("Content-Length", str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)

    def log_message(self, *_a: object) -> None:  # silencia o log por requisicao
        pass


def main(argv: list[str] | None = None) -> int:
    global _servidor
    argv = argv if argv is not None else sys.argv[1:]
    abrir = "--no-browser" not in argv
    _servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"pgIndexEval Web em {url}  (Ctrl+C ou botao 'Encerrar aplicacao' para sair)")
    if abrir:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        _servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        _servidor.server_close()
    print("Aplicacao encerrada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
