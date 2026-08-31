"""
Entrypoint da Vercel para a API read-only do PIL.

A Vercel espera encontrar uma app ASGI chamada `app` neste módulo. O código
real vive em core/step5_api.py — aqui só ajustamos o sys.path, porque na
função serverless o processo roda a partir da raiz do projeto e os módulos do
pipeline se importam entre si por nome curto (`from database import ...`).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)

from step5_api import app  # noqa: E402,F401
