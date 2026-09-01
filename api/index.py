"""
Entrypoint da Vercel para a API read-only do PIL.

A Vercel espera encontrar uma app ASGI chamada `app` neste módulo. O código
real vive em core/step5_api.py — aqui ajustamos duas coisas do ambiente
serverless.

Primeiro o sys.path: na função, o processo roda a partir da raiz do projeto e
os módulos do pipeline se importam entre si por nome curto
(`from database import ...`).

Segundo o caminho da requisição. O rewrite declarado em vercel.json manda
todas as rotas para /api/index, e é esse caminho já reescrito que chega à
aplicação — não o original. Sem desfazer isso, nenhuma rota do FastAPI casa e
tudo responde 404, inclusive `/`.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)

from step5_api import app as _app  # noqa: E402

_PREFIX = "/api/index"


async def app(scope, receive, send):
    """Remove o prefixo do rewrite antes de entregar ao FastAPI."""
    if scope.get("type") in ("http", "websocket"):
        path = scope.get("path", "")
        if path.startswith(_PREFIX):
            restored = path[len(_PREFIX):] or "/"
            scope = dict(scope, path=restored, raw_path=restored.encode())
    await _app(scope, receive, send)
