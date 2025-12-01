"""
API handler para Vercel Serverless Functions
"""
import sys
import os

# Adiciona o diretório raiz ao path
root_dir = os.path.join(os.path.dirname(__file__), '..')
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Muda para o diretório raiz
os.chdir(root_dir)

# Importa o app Flask
from app.server import app

# A Vercel espera que o app Flask seja exportado diretamente
# O objeto Flask app é WSGI-compatible
